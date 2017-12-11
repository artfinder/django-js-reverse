# -*- coding: utf-8 -*-
import re
import sys

from django.conf import settings
from django.core import urlresolvers
from django.core.exceptions import ImproperlyConfigured
from django.template import loader

from . import rjsmin
from .js_reverse_settings import (JS_EXCLUDE_NAMESPACES, JS_GLOBAL_OBJECT_NAME,
                                  JS_INCLUDE_ONLY_NAMESPACES, JS_MINIFY,
                                  JS_VAR_NAME)

if sys.version < '3':
    text_type = unicode  # NOQA
else:
    text_type = str

JS_IDENTIFIER_RE = re.compile(r'^[$A-Z_][\dA-Z_$]*$')


def prepare_url_list(urlresolver, namespace_path='', namespace=''):
    """
    returns list of tuples [(<url_name>, <url_patern_tuple> ), ...]
    """

    for url_name in urlresolver.reverse_dict.keys():
        if isinstance(url_name, (text_type, str)):
            url_patterns = []
            for url_pattern in urlresolver.reverse_dict.getlist(url_name):
                url_patterns += [
                    [namespace_path + pat[0], pat[1]] for pat in url_pattern[0]]

            if should_include_url(namespace, url_name):
                yield [namespace + url_name, url_patterns]

    for inner_ns, (inner_ns_path, inner_urlresolver) in \
            urlresolver.namespace_dict.items():
        inner_ns_path = namespace_path + inner_ns_path
        inner_ns = namespace + inner_ns + ':'

        # if we have inner_ns_path, reconstruct a new resolver so that we can
        # handle regex substitutions within the regex of a namespace.
        if inner_ns_path:
            inner_urlresolver = urlresolvers.get_ns_resolver(inner_ns_path,
                                                             inner_urlresolver)
            inner_ns_path = ''

        for x in prepare_url_list(inner_urlresolver, inner_ns_path, inner_ns):
            yield x


def should_include_url(namespace, url_name):
    exclude_ns = getattr(settings, 'JS_REVERSE_EXCLUDE_NAMESPACES', JS_EXCLUDE_NAMESPACES)
    include_only_ns = getattr(settings, 'JS_REVERSE_INCLUDE_ONLY_NAMESPACES', JS_INCLUDE_ONLY_NAMESPACES)
    exclude_names = getattr(settings, 'JS_REVERSE_EXCLUDE_NAMES', JS_EXCLUDE_NAMESPACES)
    include_only_names = getattr(settings, 'JS_REVERSE_INCLUDE_ONLY_NAMES', JS_INCLUDE_ONLY_NAMESPACES)

    if exclude_ns and include_only_ns:
        raise ImproperlyConfigured(
            'Neither use JS_REVERSE_EXCLUDE_NAMESPACES nor JS_REVERSE_INCLUDE_ONLY_NAMESPACES setting')

    if namespace + url_name in exclude_names:
        return False

    if namespace + url_name in include_only_names:
        return True

    if exclude_ns and namespace[:-1] in exclude_ns:
        return False

    if include_only_ns and namespace[:-1] in include_only_ns:
        return True

    for ns in include_only_ns:
        if ns.endswith('\0'):
            if namespace[:-1] == ns[:-1]:
                return True

    if not namespace.endswith('\0'):
        for ns in include_only_ns:
            if ns != "" and namespace[:-1].startswith(ns):
                return True

    if include_only_ns:
        return False

    return True


def generate_js(default_urlresolver):
    js_var_name = getattr(settings, 'JS_REVERSE_JS_VAR_NAME', JS_VAR_NAME)
    if not JS_IDENTIFIER_RE.match(js_var_name.upper()):
        raise ImproperlyConfigured(
            'JS_REVERSE_JS_VAR_NAME setting "%s" is not a valid javascript identifier.' % (js_var_name))

    js_global_object_name = getattr(settings, 'JS_REVERSE_JS_GLOBAL_OBJECT_NAME', JS_GLOBAL_OBJECT_NAME)
    if not JS_IDENTIFIER_RE.match(js_global_object_name.upper()):
        raise ImproperlyConfigured(
            'JS_REVERSE_JS_GLOBAL_OBJECT_NAME setting "%s" is not a valid javascript identifier.' % (
                js_global_object_name))

    minify = getattr(settings, 'JS_REVERSE_JS_MINIFY', JS_MINIFY)
    if not isinstance(minify, bool):
        raise ImproperlyConfigured(
            'JS_REVERSE_JS_MINIFY setting "%s" is not a valid. Needs to be set to True or False.' % (minify))

    script_prefix_via_config = getattr(settings, 'JS_REVERSE_SCRIPT_PREFIX', None)
    if script_prefix_via_config:
        script_prefix = script_prefix_via_config
        if not script_prefix.endswith('/'):
            script_prefix = '{0}/'.format(script_prefix)
    else:
        script_prefix = urlresolvers.get_script_prefix()

    js_content = loader.render_to_string('django_js_reverse/urls_js.tpl', {
        'urls': sorted(list(prepare_url_list(default_urlresolver))),
        'url_prefix': script_prefix,
        'js_var_name': js_var_name,
        'js_global_object_name': js_global_object_name,
    })

    if minify:
        js_content = rjsmin.jsmin(js_content)
    return js_content

import { fuzzyRules } from './fuzzyRules.js';
import URI from 'uri-js';

export function applyFuzzyRules(path) {
  // Apply fuzzy rules to simplify the ZIM path. First matching rule is applied and
  // result is immediately returned

  for (const rule of fuzzyRules) {
    const new_path = path.replace(new RegExp(rule.match), rule.replace);
    if (new_path != path) {
      return new_path;
    }
  }
  return path;
}

export function urlRewriteFunction(
  current_url, // The current (real) url we are on
  orig_host, // The host of the original url
  orig_scheme, // The scheme of the original url
  orig_url, // The original url
  prefix, // The (absolute) prefix to add to all our urls (from where we are served))
  url, // first argument passed by wombat.JS at each invocation
  useRel,
  mod,
  doc, // last argument passed by wombat.JS at each invocation
) {
  if (!url) return url;

  // Special stuff which is not really a URI but exists in the wild
  if (['#', '{', '*'].includes(url.substring(0, 1))) return url;

  // If URI scheme is defined but not http or https, we have to not rewrite the URL
  const uri = URI.parse(url);
  if (
    typeof uri.scheme !== 'undefined' &&
    !['http', 'https'].includes(uri.scheme)
  )
    return url;

  // If url starts with prefix, we need to remove this prefix before applying usual
  // rewrite rules
  if (url.startsWith(prefix)) {
    url = uri.scheme + '://' + url.substring(prefix.length);
  }

  // This is a hack to detect improper URL encoding ; proper detection should be
  // possible with chardet or other alternatives but did not worked so far ; we hence
  // take benefit of the error below to detect improper URL encoding
  // When improper URL encoding is detected, we try to encode URL as a best-effort;
  // 'best-effort', because if some part of the URL is encoded and another part is not,
  // this will fail ... but this is a weird edge case anyway
  try {
    decodeURIComponent(URI.parse(url).path);
  } catch (e) {
    url = encodeURI(url);
  }

  // Compute the absolute URI, just like the browser would have resolved it hopefully
  const original_absolute_url = URI.resolve(orig_url, url);

  // We now have to transform this absolute URI into a normalized ZIM path entry
  const absolute_url_parts = URI.parse(original_absolute_url);

  // Let's first compute the decode host
  const serialized_host = URI.serialize(
    URI.parse('http://' + absolute_url_parts.host), // fake URI to benefit from decoding
    { iri: true }, // decode potentially puny-encoded host
  );
  const decoded_host = serialized_host.substring(7, serialized_host.length - 1);

  // And the decoded path, only exception is that an empty path must resolve to '/' path
  const decoded_path =
    !absolute_url_parts.path || absolute_url_parts.path.length === 0
      ? '/'
      : decodeURIComponent(absolute_url_parts.path);

  // And the decoded query, only exception is that + sign must resolve to ' ' to avoid confusion
  const decoded_query =
    !absolute_url_parts.query || absolute_url_parts.query.length === 0
      ? ''
      : '?' + decodeURIComponent(absolute_url_parts.query).replaceAll('+', ' ');

  // combine all decode parts to get the ZIM path
  const zimPath = decoded_host + decoded_path + decoded_query;

  // apply the fuzzy rules to the ZIM path
  const fuzzifiedPath = applyFuzzyRules(zimPath);

  // Reencode everything but '/' (we decode it afterwards for simplicity)
  const finalUrl =
    prefix + encodeURIComponent(fuzzifiedPath).replaceAll('%2F', '/');

  /*
  console.log(
    'urlRewriten:\n\t- current_url: ' +
      current_url +
      '\n\t- orig_host: ' +
      orig_host +
      '\n\t- orig_scheme: ' +
      orig_scheme +
      '\n\t- orig_url: ' +
      orig_url +
      '\n\t- prefix: ' +
      prefix +
      '\n\t- url: ' +
      url +
      '\n\t- useRel: ' +
      useRel +
      '\n\t- mod: ' +
      mod +
      '\n\t- doc: ' +
      doc +
      '\n\t- finalUrl: ' +
      finalUrl.toString() +
      '\n\t',
  );*/

  return finalUrl;
}

export function getWombatInfo(
  current_url, // The current (real) url we are on
  orig_host, // The host of the original url
  orig_scheme, // The scheme of the original url
  orig_url, // The original url
  prefix, // The (absolute) prefix to add to all our urls (from where we are served))
) {
  return {
    // The rewrite function used to rewrite our urls.
    rewrite_function: (url, useRel, mod, doc) =>
      urlRewriteFunction(
        current_url,
        orig_host,
        orig_scheme,
        orig_url,
        prefix,
        url,
        useRel,
        mod,
        doc,
      ),

    // Seems to be used only to send message to. We don't care ?
    top_url: current_url,

    // Seems to be used to generate url for blobUrl returned by SW.
    // We don't care (?)
    url: orig_url,

    // Use to timestamp message send to top frame. Don't care
    timestamp: '',

    // Use to send message to top frame and in default rewrite url function. Don't care
    request_ts: '',

    // The url on which we are served.
    prefix: prefix,

    // The default mod to use.
    mod: '',

    // Use to detect if we are framed (and send message to top frame ?)
    is_framed: false,

    // ??
    is_live: false,

    // Never used ?
    coll: '',

    // Set wombat if is proxy mode (we are not)
    proxy_magic: '',

    // This is the prefix on which we have stored our static files (needed by wombat).
    // Must not conflict with other url served.
    // Will be used by wombat to not rewrite back the url
    static_prefix: prefix + '_zim_static/',

    wombat_ts: '',

    // A delay is sec to apply to all js time (`Date.now()`, ...)
    wombat_sec: 0,

    // The scheme of the original url
    wombat_scheme: orig_scheme,

    // The host of the original url
    wombat_host: orig_host,

    // Extra options ?
    wombat_opts: {},

    // ?
    enable_auto_fetch: true,
    convert_post_to_get: true,
    target_frame: '___wb_replay_top_frame',
    isSW: true,
  };
}

export default {
  applyFuzzyRules: applyFuzzyRules,
  urlRewriteFunction: urlRewriteFunction,
  getWombatInfo: getWombatInfo,
};

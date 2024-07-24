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

export function hasAlreadyBeenRewritten(
  original_absolute_url,
  orig_url,
  uri,
  url,
) {
  // Detect (with a heuristic) that the path is most probably already rewritten and
  // must be kept as-is. We just need to detect relative links (all statically rewritten
  // links are relative) and contains a path including the hostname (which cannot be
  // joined with the orig_url since if it includes the hostname, it means it is in
  // another hostname than orig_url and will hence go one level too high in the path
  // hierarchy, hence working only on ZIM paths / relative links).
  // The heurisitic is:
  // - the link must be relative and start by going at least one level up
  // - the first non relative part of the path (i.e. not . or ..) looks like a hostname
  // (i.e. it contains a dot)
  // - the relative link, when merged with orig_url, is going exactly one "path level"
  // too high in the hierarchy
  if (typeof uri.scheme == 'undefined' && url.startsWith('../')) {
    const urlParts = url.split('/');
    const original_absolute_url1 = URI.resolve(
      orig_url,
      urlParts.slice(1).join('/'),
    );
    const original_absolute_url2 = URI.resolve(
      orig_url,
      urlParts.slice(2).join('/'),
    );
    // detect that relative link is going exactly one "path level" too high
    if (
      original_absolute_url1 == original_absolute_url &&
      original_absolute_url2 != original_absolute_url
    ) {
      const firstNonRelativePart = urlParts.find((urlPart) => urlPart !== '..');
      // detect that first non relative part of the path looks like a hostname
      if (firstNonRelativePart.indexOf('.') > -1) {
        // if all 3 conditions are true, then we assume it has already been rewritten
        return true;
      }
    }
  }
  // otherwise we don't know and assume it can be safely rewritten
  return false;
}

function removeSubsequentSlashes(value) {
  // Remove all successive occurrences of a slash `/` in a given string
  // E.g `val//ue` or `val///ue` or `val////ue` (and so on) are transformed into `value`
  return value.replace(/\/\/+/g, '/');
}

export function urlRewriteFunction(
  current_url, // The current (real) url we are on, e.g. http://library.kiwix.org/content/myzim_yyyy-mm/www.example.com/index.html
  orig_host, // The host of the original url, e.g. www.example.com
  orig_scheme, // The scheme of the original url, e.g. https
  orig_url, // The original url, e.g. https://www.example.com/index.html
  prefix, // The (absolute) prefix to add to all our urls (from where we are served), e.g. http://library.kiwix.org/content/myzim_yyyy-mm/
  url, // first argument passed by wombat.JS at each invocation, current url to rewrite, e.g. http://library.kiwix.org/content/myzim_yyyy-mm/www.example.com/image.png
  useRel,
  mod,
  doc, // last argument passed by wombat.JS at each invocation
) {
  if (!url) return url;

  // Transform URL which might be an object (detected on Chromium browsers at least)
  url = String(url);

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
  // We need to use the original URL for that to properly detect the hostname when
  // present ; current URL does not allow to do it easily
  const original_absolute_url = URI.resolve(orig_url, url);

  // Detect if url has probably already been rewritten and return as-is in such a case
  if (hasAlreadyBeenRewritten(original_absolute_url, orig_url, uri, url)) {
    return url;
  }

  // Detect (with a heuristic) that the path is most probably already rewritten and
  // must be kept as-is. We just need to detect relative links (all statically rewritten
  // links are relative) and contains a path including the hostname (which cannot be
  // joined with the orig_url since if it includes the hostname, it means it is in
  // another hostname than orig_url and will hence go one level too high in the path
  // hierarchy, hence working only on ZIM paths / relative links).
  // The heurisitic is:
  // - the link must be relative and start by going at least one level up
  // - the first non relative part of the path (i.e. not . or ..) looks like a hostname
  // (i.e. it contains a dot)
  // - the relative link, when merged with orig_url, is going exactly one "path level"
  // too high in the hierarchy
  if (typeof uri.scheme == 'undefined' && url.startsWith('../')) {
    const urlParts = url.split('/');
    const original_absolute_url1 = URI.resolve(
      orig_url,
      urlParts.slice(1).join('/'),
    );
    const original_absolute_url2 = URI.resolve(
      orig_url,
      urlParts.slice(2).join('/'),
    );
    // detect that relative link is going exactly one "path level" too high
    if (
      original_absolute_url1 == original_absolute_url &&
      original_absolute_url2 != original_absolute_url
    ) {
      const firstNonRelativePart = urlParts.find((urlPart) => urlPart !== '..');
      // detect that first non relative part of the path looks like a hostname
      if (firstNonRelativePart.indexOf('.') > -1) {
        // if all 3 conditions are true, then we do not rewrite the link at all,
        // otherwise we continue with normal rewritting
        return url;
      }
    }
  }

  // We now have to transform this absolute URI into a normalized ZIM path entry
  const absolute_url_parts = URI.parse(original_absolute_url);

  // Let's first compute the decoded host
  const serialized_host = URI.serialize(
    URI.parse('http://' + absolute_url_parts.host), // fake URI to benefit from decoding
    { iri: true }, // decode potentially puny-encoded host
  );
  const decoded_host = serialized_host.substring(7, serialized_host.length - 1);

  // And the decoded path, only exception is that an empty path must resolve to '/' path
  // (our convention, just like in Python)
  const decoded_path =
    !absolute_url_parts.path || absolute_url_parts.path.length === 0
      ? '/'
      : decodeURIComponent(absolute_url_parts.path);

  // And the decoded query, only exception is that + sign must resolve to ' ' to avoid
  // confusion (our convention, just like in Python)
  const decoded_query =
    !absolute_url_parts.query || absolute_url_parts.query.length === 0
      ? ''
      : '?' + decodeURIComponent(absolute_url_parts.query).replaceAll('+', ' ');

  // combine all decoded parts to get the ZIM path
  const zimPath =
    decoded_host + removeSubsequentSlashes(decoded_path + decoded_query);

  // apply the fuzzy rules to the ZIM path
  const fuzzifiedPath = applyFuzzyRules(zimPath);

  // Reencode everything but '/' (we decode it afterwards for simplicity)
  const finalUrl =
    prefix + encodeURIComponent(fuzzifiedPath).replaceAll('%2F', '/');

  console.debug(
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
  );

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

    // A delay in sec to apply to all js time (`Date.now()`, ...)
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

import test from 'ava';

import { urlRewriteFunction } from '../src/wombatSetup.js';

test.beforeEach((t) => {
  t.context.prefix = 'http://library.kiwix.org/content/myzim_yyyy-mm/';
  t.context.originalHost = 'www.example.com';
  t.context.originalScheme = 'https';
  t.context.documentPath = '/path1/resource1.html';
  t.context.originalUrl =
    t.context.originalScheme +
    '://' +
    t.context.originalHost +
    t.context.documentPath;
  t.context.currentUrl =
    t.context.prefix + t.context.originalHost + t.context.documentPath;
});

test('undefined', (t) => {
  t.is(
    urlRewriteFunction(
      t.context.currentUrl,
      t.context.originalHost,
      t.context.originalScheme,
      t.context.originalUrl,
      t.context.prefix,
      undefined,
      undefined,
      undefined,
      undefined,
    ),
    undefined,
  );
});

test('simpleContentCompleteUrl', (t) => {
  t.is(
    urlRewriteFunction(
      t.context.currentUrl,
      t.context.originalHost,
      t.context.originalScheme,
      t.context.originalUrl,
      t.context.prefix,
      'https://www.example.com/javascript/content.txt',
      undefined,
      undefined,
      undefined,
    ),
    'http://library.kiwix.org/content/myzim_yyyy-mm/www.example.com/javascript/content.txt',
  );
});

test('simpleContentFullUrl', (t) => {
  t.is(
    urlRewriteFunction(
      t.context.currentUrl,
      t.context.originalHost,
      t.context.originalScheme,
      t.context.originalUrl,
      t.context.prefix,
      'https://user:password@www.example.com:8888/javascript/content.txt',
      undefined,
      undefined,
      undefined,
    ),
    'http://library.kiwix.org/content/myzim_yyyy-mm/www.example.com/javascript/content.txt',
  );
});

test('simpleContentNoScheme', (t) => {
  t.is(
    urlRewriteFunction(
      t.context.currentUrl,
      t.context.originalHost,
      t.context.originalScheme,
      t.context.originalUrl,
      t.context.prefix,
      '//www.example.com/javascript/content.txt',
      undefined,
      undefined,
      undefined,
    ),
    'http://library.kiwix.org/content/myzim_yyyy-mm/www.example.com/javascript/content.txt',
  );
});

test('simpleContentEmptyPath', (t) => {
  t.is(
    urlRewriteFunction(
      t.context.currentUrl,
      t.context.originalHost,
      t.context.originalScheme,
      t.context.originalUrl,
      t.context.prefix,
      'https://www.example.com/',
      undefined,
      undefined,
      undefined,
    ),
    'http://library.kiwix.org/content/myzim_yyyy-mm/www.example.com/',
  );
});

test('simpleContentNoPath', (t) => {
  t.is(
    urlRewriteFunction(
      t.context.currentUrl,
      t.context.originalHost,
      t.context.originalScheme,
      t.context.originalUrl,
      t.context.prefix,
      'https://www.example.com',
      undefined,
      undefined,
      undefined,
    ),
    'http://library.kiwix.org/content/myzim_yyyy-mm/www.example.com/',
  );
});

test('contentWithSpecialCharsNotEncoded', (t) => {
  t.is(
    urlRewriteFunction(
      t.context.currentUrl,
      t.context.originalHost,
      t.context.originalScheme,
      t.context.originalUrl,
      t.context.prefix,
      'https://www.example.com/javascript/contént.txt',
      undefined,
      undefined,
      undefined,
    ),
    'http://library.kiwix.org/content/myzim_yyyy-mm/www.example.com/javascript/cont%C3%A9nt.txt',
  );
});

test('contentWithUTF8CharsNotEncoded', (t) => {
  t.is(
    urlRewriteFunction(
      t.context.currentUrl,
      t.context.originalHost,
      t.context.originalScheme,
      t.context.originalUrl,
      t.context.prefix,
      'https://www.example.com/javascript/cont🎁nt.txt',
      undefined,
      undefined,
      undefined,
    ),
    'http://library.kiwix.org/content/myzim_yyyy-mm/www.example.com/javascript/cont%F0%9F%8E%81nt.txt',
  );
});

test('contentWithSpecialCharsEncoded', (t) => {
  t.is(
    urlRewriteFunction(
      t.context.currentUrl,
      t.context.originalHost,
      t.context.originalScheme,
      t.context.originalUrl,
      t.context.prefix,
      'https://www.example.com/javascript/cont%C3%A9nt.txt',
      undefined,
      undefined,
      undefined,
    ),
    'http://library.kiwix.org/content/myzim_yyyy-mm/www.example.com/javascript/cont%C3%A9nt.txt',
  );
});

test('contentWithSpaceNotEncoded', (t) => {
  t.is(
    urlRewriteFunction(
      t.context.currentUrl,
      t.context.originalHost,
      t.context.originalScheme,
      t.context.originalUrl,
      t.context.prefix,
      'https://www.example.com/javascript/cont nt.txt',
      undefined,
      undefined,
      undefined,
    ),
    'http://library.kiwix.org/content/myzim_yyyy-mm/www.example.com/javascript/cont%20nt.txt',
  );
});

test('contentWithPlusNotEncoded', (t) => {
  t.is(
    urlRewriteFunction(
      t.context.currentUrl,
      t.context.originalHost,
      t.context.originalScheme,
      t.context.originalUrl,
      t.context.prefix,
      'https://www.example.com/javascript/cont+nt.txt', // + is not unreserved, it must be encoded to avoid confusion
      undefined,
      undefined,
      undefined,
    ),
    'http://library.kiwix.org/content/myzim_yyyy-mm/www.example.com/javascript/cont%2Bnt.txt',
  );
});

test('contentWithTilde', (t) => {
  t.is(
    urlRewriteFunction(
      t.context.currentUrl,
      t.context.originalHost,
      t.context.originalScheme,
      t.context.originalUrl,
      t.context.prefix,
      'https://www.example.com/javascript/cont~nt.txt', // ~ is unreserved, it must be not be encoded
      undefined,
      undefined,
      undefined,
    ),
    'http://library.kiwix.org/content/myzim_yyyy-mm/www.example.com/javascript/cont~nt.txt',
  );
});

test('contentWithHyphen', (t) => {
  t.is(
    urlRewriteFunction(
      t.context.currentUrl,
      t.context.originalHost,
      t.context.originalScheme,
      t.context.originalUrl,
      t.context.prefix,
      'https://www.example.com/javascript/cont-nt.txt', // - is unreserved, it must be not be encoded
      undefined,
      undefined,
      undefined,
    ),
    'http://library.kiwix.org/content/myzim_yyyy-mm/www.example.com/javascript/cont-nt.txt',
  );
});

test('contentWithUnderscore', (t) => {
  t.is(
    urlRewriteFunction(
      t.context.currentUrl,
      t.context.originalHost,
      t.context.originalScheme,
      t.context.originalUrl,
      t.context.prefix,
      'https://www.example.com/javascript/cont_nt.txt', // _ is unreserved, it must be not be encoded
      undefined,
      undefined,
      undefined,
    ),
    'http://library.kiwix.org/content/myzim_yyyy-mm/www.example.com/javascript/cont_nt.txt',
  );
});

test('contentWithEncodedTilde', (t) => {
  t.is(
    urlRewriteFunction(
      t.context.currentUrl,
      t.context.originalHost,
      t.context.originalScheme,
      t.context.originalUrl,
      t.context.prefix,
      'https://www.example.com/javascript/cont%7Ent.txt', // ~ is unreserved, it must be not be encoded
      undefined,
      undefined,
      undefined,
    ),
    'http://library.kiwix.org/content/myzim_yyyy-mm/www.example.com/javascript/cont~nt.txt',
  );
});

test('contentWithEncodedApostrophe', (t) => {
  t.is(
    urlRewriteFunction(
      t.context.currentUrl,
      t.context.originalHost,
      t.context.originalScheme,
      t.context.originalUrl,
      t.context.prefix,
      'https://www.example.com/javascript/cont%27nt.txt', // ' is reserved, but it is not encoded in JS
      undefined,
      undefined,
      undefined,
    ),
    "http://library.kiwix.org/content/myzim_yyyy-mm/www.example.com/javascript/cont'nt.txt",
  );
});

test('contentWithEncodedExclamationMark', (t) => {
  t.is(
    urlRewriteFunction(
      t.context.currentUrl,
      t.context.originalHost,
      t.context.originalScheme,
      t.context.originalUrl,
      t.context.prefix,
      'https://www.example.com/javascript/cont%21nt.txt', // ! is reserved, but it is not encoded in JS
      undefined,
      undefined,
      undefined,
    ),
    'http://library.kiwix.org/content/myzim_yyyy-mm/www.example.com/javascript/cont!nt.txt',
  );
});

test('contentWithEncodedQuestionMark', (t) => {
  t.is(
    urlRewriteFunction(
      t.context.currentUrl,
      t.context.originalHost,
      t.context.originalScheme,
      t.context.originalUrl,
      t.context.prefix,
      'https://www.example.com/javascript/cont%3Fnt.txt',
      undefined,
      undefined,
      undefined,
    ),
    'http://library.kiwix.org/content/myzim_yyyy-mm/www.example.com/javascript/cont%3Fnt.txt',
  );
});

test('contentWithEncodedQuestionMarkAndQueryParam', (t) => {
  t.is(
    urlRewriteFunction(
      t.context.currentUrl,
      t.context.originalHost,
      t.context.originalScheme,
      t.context.originalUrl,
      t.context.prefix,
      'https://www.example.com/javascript/cont%3Fnt.txt?query=value',
      undefined,
      undefined,
      undefined,
    ),
    'http://library.kiwix.org/content/myzim_yyyy-mm/www.example.com/javascript/cont%3Fnt.txt%3Fquery%3Dvalue',
  );
});

test('contentWithEncodedStar', (t) => {
  t.is(
    urlRewriteFunction(
      t.context.currentUrl,
      t.context.originalHost,
      t.context.originalScheme,
      t.context.originalUrl,
      t.context.prefix,
      'https://www.example.com/javascript/cont%2Ant.txt', // * is reserved, but it is not encoded in JS
      undefined,
      undefined,
      undefined,
    ),
    'http://library.kiwix.org/content/myzim_yyyy-mm/www.example.com/javascript/cont*nt.txt',
  );
});

test('contentWithEncodedParentheses', (t) => {
  t.is(
    urlRewriteFunction(
      t.context.currentUrl,
      t.context.originalHost,
      t.context.originalScheme,
      t.context.originalUrl,
      t.context.prefix,
      'https://www.example.com/javascript/cont%28%29nt.txt', // ( and ) are reserved, but they are not encoded in JS
      undefined,
      undefined,
      undefined,
    ),
    'http://library.kiwix.org/content/myzim_yyyy-mm/www.example.com/javascript/cont()nt.txt',
  );
});

test('contentWithEncodedHyphen1', (t) => {
  t.is(
    urlRewriteFunction(
      t.context.currentUrl,
      t.context.originalHost,
      t.context.originalScheme,
      t.context.originalUrl,
      t.context.prefix,
      'https://www.example.com/javascript/cont%2Dnt.txt', // - is unreserved, it must be not be encoded
      undefined,
      undefined,
      undefined,
    ),
    'http://library.kiwix.org/content/myzim_yyyy-mm/www.example.com/javascript/cont-nt.txt',
  );
});

test('contentWithEncodedHyphen2', (t) => {
  t.is(
    urlRewriteFunction(
      t.context.currentUrl,
      t.context.originalHost,
      t.context.originalScheme,
      t.context.originalUrl,
      t.context.prefix,
      'https://www.example.com/javascript/co%25nt%2Dnt.txt', // - is unreserved, it must be not be encoded
      undefined,
      undefined,
      undefined,
    ),
    'http://library.kiwix.org/content/myzim_yyyy-mm/www.example.com/javascript/co%25nt-nt.txt',
  );
});

test('contentWithEncodedUnderscore', (t) => {
  t.is(
    urlRewriteFunction(
      t.context.currentUrl,
      t.context.originalHost,
      t.context.originalScheme,
      t.context.originalUrl,
      t.context.prefix,
      'https://www.example.com/javascript/cont%5Fnt.txt', // _ is unreserved, it must be not be encoded
      undefined,
      undefined,
      undefined,
    ),
    'http://library.kiwix.org/content/myzim_yyyy-mm/www.example.com/javascript/cont_nt.txt',
  );
});

test('contentWithEncodedPeriod', (t) => {
  t.is(
    urlRewriteFunction(
      t.context.currentUrl,
      t.context.originalHost,
      t.context.originalScheme,
      t.context.originalUrl,
      t.context.prefix,
      'https://www.example.com/javascript/content%2Etxt', // . is unreserved, it must be not be encoded
      undefined,
      undefined,
      undefined,
    ),
    'http://library.kiwix.org/content/myzim_yyyy-mm/www.example.com/javascript/content.txt',
  );
});

test('contentWithSimpleQueryString', (t) => {
  t.is(
    urlRewriteFunction(
      t.context.currentUrl,
      t.context.originalHost,
      t.context.originalScheme,
      t.context.originalUrl,
      t.context.prefix,
      'https://www.example.com/javascript/content.txt?query=value',
      undefined,
      undefined,
      undefined,
    ),
    'http://library.kiwix.org/content/myzim_yyyy-mm/www.example.com/javascript/content.txt%3Fquery%3Dvalue',
  );
});

test('contentWithQueryValueEqualSign', (t) => {
  t.is(
    urlRewriteFunction(
      t.context.currentUrl,
      t.context.originalHost,
      t.context.originalScheme,
      t.context.originalUrl,
      t.context.prefix,
      'https://www.example.com/javascript/content.txt?query=val%3Deue',
      undefined,
      undefined,
      undefined,
    ),
    'http://library.kiwix.org/content/myzim_yyyy-mm/www.example.com/javascript/content.txt%3Fquery%3Dval%3Deue',
  );
});

test('contentWithQueryValuePercentSign', (t) => {
  t.is(
    urlRewriteFunction(
      t.context.currentUrl,
      t.context.originalHost,
      t.context.originalScheme,
      t.context.originalUrl,
      t.context.prefix,
      'https://www.example.com/javascript/content.txt?query=val%25eue',
      undefined,
      undefined,
      undefined,
    ),
    'http://library.kiwix.org/content/myzim_yyyy-mm/www.example.com/javascript/content.txt%3Fquery%3Dval%25eue',
  );
});

test('contentWithQueryParamPercentSign', (t) => {
  t.is(
    urlRewriteFunction(
      t.context.currentUrl,
      t.context.originalHost,
      t.context.originalScheme,
      t.context.originalUrl,
      t.context.prefix,
      'https://www.example.com/javascript/content.txt?que%25ry=valeue',
      undefined,
      undefined,
      undefined,
    ),
    'http://library.kiwix.org/content/myzim_yyyy-mm/www.example.com/javascript/content.txt%3Fque%25ry%3Dvaleue',
  );
});

test('contentWithQueryParamPlusSign', (t) => {
  t.is(
    urlRewriteFunction(
      t.context.currentUrl,
      t.context.originalHost,
      t.context.originalScheme,
      t.context.originalUrl,
      t.context.prefix,
      'https://www.example.com/javascript/content.txt?param=val+ue',
      undefined,
      undefined,
      undefined,
    ),
    'http://library.kiwix.org/content/myzim_yyyy-mm/www.example.com/javascript/content.txt%3Fparam%3Dval%20ue',
  );
});

test('fqdnWithSpecialCharsEncoded', (t) => {
  t.is(
    urlRewriteFunction(
      t.context.currentUrl,
      t.context.originalHost,
      t.context.originalScheme,
      t.context.originalUrl,
      t.context.prefix,
      'https://www.xn--xample-9ua.com/javascript/content.txt',
      undefined,
      undefined,
      undefined,
    ),
    'http://library.kiwix.org/content/myzim_yyyy-mm/www.%C3%A9xample.com/javascript/content.txt',
  );
});

test('fqdnWithSpecialCharsNotEncoded', (t) => {
  t.is(
    urlRewriteFunction(
      t.context.currentUrl,
      t.context.originalHost,
      t.context.originalScheme,
      t.context.originalUrl,
      t.context.prefix,
      'https://www.éxample.com/javascript/content.txt',
      undefined,
      undefined,
      undefined,
    ),
    'http://library.kiwix.org/content/myzim_yyyy-mm/www.%C3%A9xample.com/javascript/content.txt',
  );
});

test('fqdnWithSpecialCharsEncodedContentWithSpecialCharsEncoded', (t) => {
  t.is(
    urlRewriteFunction(
      t.context.currentUrl,
      t.context.originalHost,
      t.context.originalScheme,
      t.context.originalUrl,
      t.context.prefix,
      'https://www.xn--xample-9ua.com/javascript/cont%C3%A9nt.txt',
      undefined,
      undefined,
      undefined,
    ),
    'http://library.kiwix.org/content/myzim_yyyy-mm/www.%C3%A9xample.com/javascript/cont%C3%A9nt.txt',
  );
});

test('relSimpleContent1', (t) => {
  t.is(
    urlRewriteFunction(
      t.context.currentUrl,
      t.context.originalHost,
      t.context.originalScheme,
      t.context.originalUrl,
      t.context.prefix,
      '../javascript/content.txt',
      undefined,
      undefined,
      undefined,
    ),
    'http://library.kiwix.org/content/myzim_yyyy-mm/www.example.com/javascript/content.txt',
  );
});

test('relSimpleContent2', (t) => {
  t.is(
    urlRewriteFunction(
      t.context.currentUrl,
      t.context.originalHost,
      t.context.originalScheme,
      t.context.originalUrl,
      t.context.prefix,
      './javascript/content.txt',
      undefined,
      undefined,
      undefined,
    ),
    'http://library.kiwix.org/content/myzim_yyyy-mm/www.example.com/path1/javascript/content.txt',
  );
});

test('relGoingUperThanHost', (t) => {
  t.is(
    urlRewriteFunction(
      t.context.currentUrl,
      t.context.originalHost,
      t.context.originalScheme,
      t.context.originalUrl,
      t.context.prefix,
      '../../../../javascript/content.txt', // this is too many .. ; at this stage it means host home folder
      undefined,
      undefined,
      undefined,
    ),
    'http://library.kiwix.org/content/myzim_yyyy-mm/www.example.com/javascript/content.txt',
  );
});

test('relSimpleContent3', (t) => {
  t.is(
    urlRewriteFunction(
      t.context.currentUrl,
      t.context.originalHost,
      t.context.originalScheme,
      t.context.originalUrl,
      t.context.prefix,
      '/javascript/content.txt',
      undefined,
      undefined,
      undefined,
    ),
    'http://library.kiwix.org/content/myzim_yyyy-mm/www.example.com/javascript/content.txt',
  );
});

test('mailto', (t) => {
  t.is(
    urlRewriteFunction(
      t.context.currentUrl,
      t.context.originalHost,
      t.context.originalScheme,
      t.context.originalUrl,
      t.context.prefix,
      'mailto:bob@example.com',
      undefined,
      undefined,
      undefined,
    ),
    'mailto:bob@example.com',
  );
});

test('data', (t) => {
  t.is(
    urlRewriteFunction(
      t.context.currentUrl,
      t.context.originalHost,
      t.context.originalScheme,
      t.context.originalUrl,
      t.context.prefix,
      'data:bob@example.com',
      undefined,
      undefined,
      undefined,
    ),
    'data:bob@example.com',
  );
});

test('tel', (t) => {
  t.is(
    urlRewriteFunction(
      t.context.currentUrl,
      t.context.originalHost,
      t.context.originalScheme,
      t.context.originalUrl,
      t.context.prefix,
      'tel:+1.43.88.999.999',
      undefined,
      undefined,
      undefined,
    ),
    'tel:+1.43.88.999.999',
  );
});

test('ftp', (t) => {
  t.is(
    urlRewriteFunction(
      t.context.currentUrl,
      t.context.originalHost,
      t.context.originalScheme,
      t.context.originalUrl,
      t.context.prefix,
      'ftp://www.example.com/javascript/content.txt',
      undefined,
      undefined,
      undefined,
    ),
    'ftp://www.example.com/javascript/content.txt',
  );
});

test('blob', (t) => {
  t.is(
    urlRewriteFunction(
      t.context.currentUrl,
      t.context.originalHost,
      t.context.originalScheme,
      t.context.originalUrl,
      t.context.prefix,
      'blob:exemple.com/url',
      undefined,
      undefined,
      undefined,
    ),
    'blob:exemple.com/url',
  );
});

test('customprotocol', (t) => {
  t.is(
    urlRewriteFunction(
      t.context.currentUrl,
      t.context.originalHost,
      t.context.originalScheme,
      t.context.originalUrl,
      t.context.prefix,
      'customprotocol:exemple.com/url',
      undefined,
      undefined,
      undefined,
    ),
    'customprotocol:exemple.com/url',
  );
});

test('anchor', (t) => {
  t.is(
    urlRewriteFunction(
      t.context.currentUrl,
      t.context.originalHost,
      t.context.originalScheme,
      t.context.originalUrl,
      t.context.prefix,
      '#anchor',
      undefined,
      undefined,
      undefined,
    ),
    '#anchor',
  );
});

test('star', (t) => {
  t.is(
    urlRewriteFunction(
      t.context.currentUrl,
      t.context.originalHost,
      t.context.originalScheme,
      t.context.originalUrl,
      t.context.prefix,
      '*wtf',
      undefined,
      undefined,
      undefined,
    ),
    '*wtf',
  );
});

test('mustache', (t) => {
  t.is(
    urlRewriteFunction(
      t.context.currentUrl,
      t.context.originalHost,
      t.context.originalScheme,
      t.context.originalUrl,
      t.context.prefix,
      '{wtf',
      undefined,
      undefined,
      undefined,
    ),
    '{wtf',
  );
});

test('youtubeFuzzyNotEncoded', (t) => {
  t.is(
    urlRewriteFunction(
      t.context.currentUrl,
      t.context.originalHost,
      t.context.originalScheme,
      t.context.originalUrl,
      t.context.prefix,
      'www.youtube.com/get_video_info?video_id=123ah',
      undefined,
      undefined,
      undefined,
    ),
    'http://library.kiwix.org/content/myzim_yyyy-mm/www.example.com/path1/youtube.fuzzy.replayweb.page/get_video_info%3Fvideo_id%3D123ah',
  );
});

test('youtubeFuzzyEncoded', (t) => {
  t.is(
    urlRewriteFunction(
      t.context.currentUrl,
      t.context.originalHost,
      t.context.originalScheme,
      t.context.originalUrl,
      t.context.prefix,
      'www.youtube.com/get_video_info?video_id=12%3D3ah',
      undefined,
      undefined,
      undefined,
    ),
    'http://library.kiwix.org/content/myzim_yyyy-mm/www.example.com/path1/youtube.fuzzy.replayweb.page/get_video_info%3Fvideo_id%3D12%3D3ah',
  );
});

test('alreadyRewritenUrlSimple', (t) => {
  t.is(
    urlRewriteFunction(
      t.context.currentUrl,
      t.context.originalHost,
      t.context.originalScheme,
      t.context.originalUrl,
      t.context.prefix,
      'http://library.kiwix.org/content/myzim_yyyy-mm/www.example.com/javascript/content.txt',
      undefined,
      undefined,
      undefined,
    ),
    'http://library.kiwix.org/content/myzim_yyyy-mm/www.example.com/javascript/content.txt',
  );
});

test('alreadyRewritenUrlSpecialCharsNotEncoded', (t) => {
  t.is(
    urlRewriteFunction(
      t.context.currentUrl,
      t.context.originalHost,
      t.context.originalScheme,
      t.context.originalUrl,
      t.context.prefix,
      'http://library.kiwix.org/content/myzim_yyyy-mm/www.example.com/javascript/contént.txt',
      undefined,
      undefined,
      undefined,
    ),
    'http://library.kiwix.org/content/myzim_yyyy-mm/www.example.com/javascript/cont%C3%A9nt.txt',
  );
});

test('alreadyRewritenUrlUTF8CharsNotEncoded', (t) => {
  t.is(
    urlRewriteFunction(
      t.context.currentUrl,
      t.context.originalHost,
      t.context.originalScheme,
      t.context.originalUrl,
      t.context.prefix,
      'http://library.kiwix.org/content/myzim_yyyy-mm/www.example.com/javascript/cont🎁nt.txt',
      undefined,
      undefined,
      undefined,
    ),
    'http://library.kiwix.org/content/myzim_yyyy-mm/www.example.com/javascript/cont%F0%9F%8E%81nt.txt',
  );
});

test('simpleContentDomainNameInPath1', (t) => {
  t.is(
    urlRewriteFunction(
      t.context.currentUrl,
      t.context.originalHost,
      t.context.originalScheme,
      t.context.originalUrl,
      t.context.prefix,
      'https://www.example.com/www.example.com/content.txt',
      undefined,
      undefined,
      undefined,
    ),
    'http://library.kiwix.org/content/myzim_yyyy-mm/www.example.com/www.example.com/content.txt',
  );
});

test('simpleContentDomainNameInPath2', (t) => {
  t.is(
    urlRewriteFunction(
      t.context.currentUrl,
      t.context.originalHost,
      t.context.originalScheme,
      t.context.originalUrl,
      t.context.prefix,
      'https://www.example.com/javascript/www.example.com',
      undefined,
      undefined,
      undefined,
    ),
    'http://library.kiwix.org/content/myzim_yyyy-mm/www.example.com/javascript/www.example.com',
  );
});

// URL has already been statically rewritten and originally had a query parameter
test('relAlreadyEncoded', (t) => {
  t.is(
    urlRewriteFunction(
      t.context.currentUrl,
      t.context.originalHost,
      t.context.originalScheme,
      t.context.originalUrl,
      t.context.prefix,
      '../javascript/content.txt%3Fquery%3Dvalue',
      undefined,
      undefined,
      undefined,
    ),
    'http://library.kiwix.org/content/myzim_yyyy-mm/www.example.com/javascript/content.txt%3Fquery%3Dvalue',
  );
});

// this is an edge case where the URL has already been statically rewritten and is located
// on a different domain name => we do not touch it at all
test('relAnotherHostAlreadyRewritten', (t) => {
  t.is(
    urlRewriteFunction(
      t.context.currentUrl,
      t.context.originalHost,
      t.context.originalScheme,
      t.context.originalUrl,
      t.context.prefix,
      '../../anotherhost.com/javascript/content.txt',
      undefined,
      undefined,
      undefined,
    ),
    '../../anotherhost.com/javascript/content.txt',
  );
});

// this is an edge case where the URL has already been statically rewritten and is located
// on a different domain name => we do not touch it at all
test('relAnotherHostAlreadyRewrittenRootPath', (t) => {
  const documentPath = '/';
  const originalUrl =
    t.context.originalScheme + '://' + t.context.originalHost + documentPath;
  const currentUrl = t.context.prefix + t.context.originalHost + documentPath;
  t.is(
    urlRewriteFunction(
      currentUrl,
      t.context.originalHost,
      t.context.originalScheme,
      originalUrl,
      t.context.prefix,
      '../anotherhost.com/javascript/content.txt',
      undefined,
      undefined,
      undefined,
    ),
    '../anotherhost.com/javascript/content.txt',
  );
});

// this is an edge case where the URL has already been statically rewritten and is located
// on a different domain name => we do not touch it at all
test('relAnotherHostAlreadyRewrittenEmptyPath', (t) => {
  const documentPath = '';
  const originalUrl =
    t.context.originalScheme + '://' + t.context.originalHost + documentPath;
  const currentUrl = t.context.prefix + t.context.originalHost + documentPath;
  t.is(
    urlRewriteFunction(
      currentUrl,
      t.context.originalHost,
      t.context.originalScheme,
      originalUrl,
      t.context.prefix,
      '../anotherhost.com/javascript/content.txt',
      undefined,
      undefined,
      undefined,
    ),
    '../anotherhost.com/javascript/content.txt',
  );
});

// this is an edge case where the URL has already been statically rewritten and is located
// on a different fuzzified domain name => we do not touch it at all
test('relAnotherFuzzifiedHostAlreadyRewritten', (t) => {
  t.is(
    urlRewriteFunction(
      t.context.currentUrl,
      t.context.originalHost,
      t.context.originalScheme,
      t.context.originalUrl,
      t.context.prefix,
      '../../youtube.fuzzy.replayweb.page/get_video_info%3Fvideo_id%3D123ah',
      undefined,
      undefined,
      undefined,
    ),
    '../../youtube.fuzzy.replayweb.page/get_video_info%3Fvideo_id%3D123ah',
  );
});

// this is an edge case where the URL might looks like it has already been statically
// rewritten since it is going too up exactly by one level but it does not looks like a
// hostname at all => we rewrite it again
test('relTooUpNotLookingLikeAHostname', (t) => {
  t.is(
    urlRewriteFunction(
      t.context.currentUrl,
      t.context.originalHost,
      t.context.originalScheme,
      t.context.originalUrl,
      t.context.prefix,
      '../../javascript/content.txt', // this is too many .. ; at this stage it means host home folder
      undefined,
      undefined,
      undefined,
    ),
    'http://library.kiwix.org/content/myzim_yyyy-mm/www.example.com/javascript/content.txt',
  );
});

// this is an edge case where the URL might looks like it has already been statically
// rewritten since it is going too up exactly by one level but it does not looks like a
// hostname at all => we rewrite it again
test('relTooUpNotLookingLikeAHostnameRootPath', (t) => {
  const documentPath = '/';
  const originalUrl =
    t.context.originalScheme + '://' + t.context.originalHost + documentPath;
  const currentUrl = t.context.prefix + t.context.originalHost + documentPath;
  t.is(
    urlRewriteFunction(
      currentUrl,
      t.context.originalHost,
      t.context.originalScheme,
      originalUrl,
      t.context.prefix,
      '../javascript/content.txt',
      undefined,
      undefined,
      undefined,
    ),
    'http://library.kiwix.org/content/myzim_yyyy-mm/www.example.com/javascript/content.txt',
  );
});

// this is an edge case where the URL might looks like it has already been statically
// rewritten since it is going too up exactly by one level but it does not looks like a
// hostname at all => we rewrite it again
test('relTooUpNotLookingLikeAHostnameEmptyPath', (t) => {
  const documentPath = '';
  const originalUrl =
    t.context.originalScheme + '://' + t.context.originalHost + documentPath;
  const currentUrl = t.context.prefix + t.context.originalHost + documentPath;
  t.is(
    urlRewriteFunction(
      currentUrl,
      t.context.originalHost,
      t.context.originalScheme,
      originalUrl,
      t.context.prefix,
      '../javascript/content.txt',
      undefined,
      undefined,
      undefined,
    ),
    'http://library.kiwix.org/content/myzim_yyyy-mm/www.example.com/javascript/content.txt',
  );
});

// this is an edge case where the URL might looks like it has already been statically
// rewritten and is located on a different domain name but it is going to way up in the
// hierarchy so it is most probably not really rewritten yet => we rewrite it again
test('relNotReallyAnotherHostAlreadyRewrittenTooUp', (t) => {
  t.is(
    urlRewriteFunction(
      t.context.currentUrl,
      t.context.originalHost,
      t.context.originalScheme,
      t.context.originalUrl,
      t.context.prefix,
      '../../../anotherhost.com/javascript/content.txt',
      undefined,
      undefined,
      undefined,
    ),
    'http://library.kiwix.org/content/myzim_yyyy-mm/www.example.com/anotherhost.com/javascript/content.txt',
  );
});

// this is an edge case where the URL might looks like it has already been statically
// rewritten and is located on a different domain name but it is going no enough way up
// in the hierarchy so it is most probably not really rewritten yet => we rewrite it
// again
test('relNotReallyAnotherHostAlreadyRewrittenNotUpEnough', (t) => {
  t.is(
    urlRewriteFunction(
      t.context.currentUrl,
      t.context.originalHost,
      t.context.originalScheme,
      t.context.originalUrl,
      t.context.prefix,
      '../anotherhost.com/javascript/content.txt',
      undefined,
      undefined,
      undefined,
    ),
    'http://library.kiwix.org/content/myzim_yyyy-mm/www.example.com/anotherhost.com/javascript/content.txt',
  );
});

test('doubleSlash1', (t) => {
  t.is(
    urlRewriteFunction(
      t.context.currentUrl,
      t.context.originalHost,
      t.context.originalScheme,
      t.context.originalUrl,
      t.context.prefix,
      'http://example.com/some/path/http://example.com//some/path',
      undefined,
      undefined,
      undefined,
    ),
    'http://library.kiwix.org/content/myzim_yyyy-mm/example.com/some/path/http%3A/example.com/some/path',
  );
});

test('doubleSlash2', (t) => {
  t.is(
    urlRewriteFunction(
      t.context.currentUrl,
      t.context.originalHost,
      t.context.originalScheme,
      t.context.originalUrl,
      t.context.prefix,
      'http://example.com/some/pa?th/http://example.com//some/path',
      undefined,
      undefined,
      undefined,
    ),
    'http://library.kiwix.org/content/myzim_yyyy-mm/example.com/some/pa%3Fth/http%3A/example.com/some/path',
  );
});

test('doubleSlash3', (t) => {
  t.is(
    urlRewriteFunction(
      t.context.currentUrl,
      t.context.originalHost,
      t.context.originalScheme,
      t.context.originalUrl,
      t.context.prefix,
      'http://example.com/so?me/pa?th/http://example.com//some/path',
      undefined,
      undefined,
      undefined,
    ),
    'http://library.kiwix.org/content/myzim_yyyy-mm/example.com/so%3Fme/pa%3Fth/http%3A/example.com/some/path',
  );
});

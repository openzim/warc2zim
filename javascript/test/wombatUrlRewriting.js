import test from 'ava';

import { urlRewriteFunction } from '../src/wombatSetup.js';
import { createGzip } from 'zlib';

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

// Why? I don't get it ... this is not supposed to be a valid URL ...
test('originalHost', (t) => {
  t.is(
    urlRewriteFunction(
      t.context.currentUrl,
      t.context.originalHost,
      t.context.originalScheme,
      t.context.originalUrl,
      t.context.prefix,
      'www.example.com/javascript/content.txt',
      undefined,
      undefined,
      undefined,
    ),
    'www.example.com/javascript/content.txt',
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

test.skip('simpleContentFullUrl', (t) => {
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

test.skip('contentWithPlusNotEncoded', (t) => {
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

test.skip('contentWithEncodedTilde', (t) => {
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

test.skip('contentWithEncodedApostrophe', (t) => {
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

test.skip('contentWithEncodedExclamationMark', (t) => {
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

test.skip('contentWithEncodedStar', (t) => {
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

test.skip('contentWithEncodedParentheses', (t) => {
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

test.skip('contentWithEncodedHyphen1', (t) => {
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

test.skip('contentWithEncodedHyphen2', (t) => {
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

test.skip('contentWithEncodedUnderscore', (t) => {
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

test.skip('contentWithEncodedPeriod', (t) => {
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

test.skip('contentWithQueryValueEqualSign', (t) => {
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

test.skip('contentWithQueryValuePercentSign', (t) => {
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

test.skip('contentWithQueryParamPercentSign', (t) => {
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

test.skip('contentWithQueryParamPlusSign', (t) => {
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

test.skip('fqdnWithSpecialCharsEncoded', (t) => {
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

test.skip('fqdnWithSpecialCharsNotEncoded', (t) => {
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

test.skip('fqdnWithSpecialCharsEncodedContentWithSpecialCharsEncoded', (t) => {
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

test.skip('relGoingUperThanHost', (t) => {
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

test.skip('tel', (t) => {
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

test.skip('ftp', (t) => {
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

test.skip('blob', (t) => {
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

test.skip('customprotocol', (t) => {
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

test.skip('youtubeFuzzyEncoded', (t) => {
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
    'http://library.kiwix.org/content/myzim_yyyy-mm/www.example.com/path1/youtube.fuzzy.replayweb.page/get_video_info%3Fvideo_id%3D12%3D3',
  );
});

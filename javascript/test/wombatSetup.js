import test from 'ava';

import utils from '../src/wombatSetup.js';

test.beforeEach((t) => {
  t.context.prefix = 'http://library.kiwix.org/content/myzim_yyyy-mm/';
  t.context.originalHost = 'www.example.com';
  t.context.originalScheme = 'https';
});

test('nominalWbInfo', (t) => {
  const path = 'path1/resource1.js';
  const originalUrl =
    t.context.originalScheme + '://' + t.context.originalHost + '/' + path;
  const wmInfo = utils.getWombatInfo(
    t.context.prefix + path,
    t.context.originalHost,
    t.context.originalScheme,
    originalUrl,
    t.context.prefix,
  );
  t.is(wmInfo.coll, '');
  t.is(wmInfo.convert_post_to_get, true);
  t.is(wmInfo.enable_auto_fetch, true);
  t.is(wmInfo.isSW, true);
  t.is(wmInfo.is_framed, false);
  t.is(wmInfo.is_live, false);
  t.is(wmInfo.mod, '');
  t.is(wmInfo.prefix, t.context.prefix);
  t.is(wmInfo.proxy_magic, '');
  t.is(wmInfo.request_ts, '');
  t.is(wmInfo.static_prefix, t.context.prefix + '_zim_static/');
  t.is(wmInfo.target_frame, '___wb_replay_top_frame');
  t.is(wmInfo.timestamp, '');
  t.is(wmInfo.top_url, t.context.prefix + path);
  t.is(wmInfo.url, originalUrl);
  t.is(wmInfo.wombat_host, t.context.originalHost);
  t.deepEqual(wmInfo.wombat_opts, {});
  t.is(wmInfo.wombat_scheme, t.context.originalScheme);
  t.is(wmInfo.wombat_sec, 0);
  t.is(wmInfo.wombat_ts, '');
});

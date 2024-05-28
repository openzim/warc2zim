import test from 'ava';

import { applyFuzzyRules } from '../src/wombatSetup.js';

test('i.ytimg.com_1', (t) => {
  t.is(
    applyFuzzyRules(
      'i.ytimg.com/vi/-KpLmsAR23I/maxresdefault.jpg?sqp=-oaymwEmCIAKENAF8quKqQMa8AEB-AH-CYAC0AWKAgwIABABGHIgTyg-MA8=&rs=AOn4CLDr-FmDmP3aCsD84l48ygBmkwHg-g',
    ),
    'i.ytimg.com.fuzzy.replayweb.page/vi/-KpLmsAR23I/thumbnail.jpg',
  );
});

test('i.ytimg.com_2', (t) => {
  t.is(
    applyFuzzyRules(
      'i.ytimg.com/vi/-KpLmsAR23I/maxresdefault.png?sqp=-oaymwEmCIAKENAF8quKqQMa8AEB-AH-CYAC0AWKAgwIABABGHIgTyg-MA8=&rs=AOn4CLDr-FmDmP3aCsD84l48ygBmkwHg-g',
    ),
    'i.ytimg.com.fuzzy.replayweb.page/vi/-KpLmsAR23I/thumbnail.png',
  );
});

test('i.ytimg.com_3', (t) => {
  t.is(
    applyFuzzyRules('i.ytimg.com/vi/-KpLmsAR23I/maxresdefault.jpg'),
    'i.ytimg.com.fuzzy.replayweb.page/vi/-KpLmsAR23I/thumbnail.jpg',
  );
});

test('i.ytimg.com_4', (t) => {
  t.is(
    applyFuzzyRules('i.ytimg.com/vi/-KpLmsAR23I/max-res.default.jpg'),
    'i.ytimg.com.fuzzy.replayweb.page/vi/-KpLmsAR23I/thumbnail.jpg',
  );
});

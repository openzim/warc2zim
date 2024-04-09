import path from 'path';
import url from 'url';

import { nodeResolve } from '@rollup/plugin-node-resolve';
import terser from '@rollup/plugin-terser';

const __filename = url.fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const outputDir =
  process.env.OUTPUT_DIR || path.join(__dirname, '../src/warc2zim/statics');

const noStrict = {
  renderChunk(code) {
    return code.replace("'use strict';", '');
  },
};

const watchOptions = {
  exclude: 'node_modules/**',
  chokidar: {
    alwaysStat: true,
    usePolling: true,
  },
};

const wombatSetup = {
  input: 'src/wombatSetup.js',
  output: {
    name: 'wombatSetup',
    file: path.join(outputDir, 'wombatSetup.js'),
    sourcemap: false,
    format: 'iife',
    exports: 'named',
  },
  watch: watchOptions,
  plugins: [nodeResolve(), noStrict, terser()],
};

export default wombatSetup;

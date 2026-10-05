import {readdirSync, readFileSync} from 'node:fs';
import {join} from 'node:path';

// Inspect the built server dependency traces, not npm's prod/dev labels.
const traces = [];
function walk(directory) {
  for (const item of readdirSync(directory, {withFileTypes:true})) {
    const file = join(directory, item.name);
    if (item.isDirectory()) walk(file);
    else if (file.endsWith('.nft.json')) traces.push(file);
  }
}
walk('apps/admin-web/.next');
const references = [];
for (const trace of traces) {
  for (const entry of JSON.parse(readFileSync(trace, 'utf8')).files) {
    if (/node_modules\/(braces|node-forge)\//.test(entry.replaceAll('\\', '/'))) {
      references.push({trace, entry});
    }
  }
}
console.log(JSON.stringify({traces:traces.length, advisoryPackageReferences:references}, null, 2));
if (!traces.length || references.length) {
  console.error('Web runtime surface verification FAIL: missing traces or advisory package present.');
  process.exit(1);
}

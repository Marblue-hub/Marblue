// Native report canvas snapshots using Microsoft's public Desktop Bridge.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { BridgeClient } from '../.tools/pbi-author/node_modules/@microsoft/powerbi-desktop-bridge-cli/dist/index.js';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const pid = Number(process.argv[2]);
if (!pid) throw new Error('Usage: node scripts/capture_powerbi_pages.mjs <Desktop PID>');
const pages=JSON.parse(fs.readFileSync(path.join(root,'reports/powerbi_build.json'),'utf8')).pages;
const out=path.join(root,'reports/powerbi/screenshots');
fs.mkdirSync(out,{recursive:true});
const client=await new BridgeClient(pid).connect();
try {
    const manifest=await client.manifest();
    if (!manifest.methods.some(m=>m.name==='report.snapshot.capture/v2')) throw new Error('Canvas snapshot v2 is unavailable.');
    for (const page of pages) {
        const pageId=page.id;
        const result=await client.sendBridgeMethod('report.snapshot.capture/v2',{
            pageId,scale:1,region:{x:0,y:0,width:1280,height:720}});
        const target=path.join(out,page.page+'.png');
        fs.writeFileSync(target,Buffer.from(result.payload,'base64'));
        console.log(JSON.stringify({pageId,title:page.page,path:target}));
    }
} finally {client.dispose();}

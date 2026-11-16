// Fixed public endpoints only; TLS verification stays enabled.
const endpoints={suggestions:'https://marketdesk-source-suggestions.source-suggestions.workers.dev/suggestions',catalog:'https://caruanatheo-beep.github.io/Internships-Offres/sources.json'};
async function main(){
 const url=endpoints[process.argv[2]];if(!url)throw Error('Invalid endpoint');
 const response=await fetch(url,{headers:{Origin:'https://caruanatheo-beep.github.io'},redirect:'error',signal:AbortSignal.timeout(12000)});
 if(!response.ok)throw Error('Public metadata unavailable');
 const chunks=[];let size=0;
 for await(const chunk of response.body){size+=chunk.length;if(size>256000)throw Error('Size limit');chunks.push(chunk);}
 const data=JSON.parse(Buffer.concat(chunks).toString('utf8'));
 process.stdout.write(JSON.stringify(data));
}
main().catch(()=>{process.stderr.write('Public metadata unavailable');process.exitCode=1;});

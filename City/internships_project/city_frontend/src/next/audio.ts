// Generated in the browser: a slow lofi loop and short interface sounds. No audio files.
let context: AudioContext | null = null;
let musicGain: GainNode | null = null;
let timer = 0, nextBeat = 0, beat = 0;
const audio = (): AudioContext => (context ??= new AudioContext());

const CHORDS = [[146.83, 174.61, 220, 261.63, 329.63], [130.81, 164.81, 196, 246.94, 293.66],
  [116.54, 146.83, 174.61, 220, 261.63], [110, 138.59, 164.81, 196, 246.94]];

function noise(ctx: AudioContext, seconds: number): AudioBuffer {
  const buffer = ctx.createBuffer(1, ctx.sampleRate * seconds, ctx.sampleRate), data = buffer.getChannelData(0);
  for (let i = 0; i < data.length; i++) data[i] = Math.random() * 2 - 1;
  return buffer;
}

function schedule(ctx: AudioContext, out: GainNode, when: number, index: number): void {
  const stepInBar = index % 8;
  if (stepInBar === 0) { // Soft electric-piano chord, one per bar.
    const filter = ctx.createBiquadFilter(); filter.type = "lowpass"; filter.frequency.value = 850; filter.connect(out);
    CHORDS[Math.floor(index / 8) % CHORDS.length].forEach((frequency, i) => {
      const osc = ctx.createOscillator(), gain = ctx.createGain();
      osc.type = i % 2 ? "sine" : "triangle"; osc.frequency.value = frequency; osc.detune.value = (i - 2) * 4;
      gain.gain.setValueAtTime(0, when + i * 0.03); gain.gain.linearRampToValueAtTime(0.11, when + 0.08 + i * 0.03);
      gain.gain.exponentialRampToValueAtTime(0.001, when + 3.2);
      osc.connect(gain); gain.connect(filter); osc.start(when); osc.stop(when + 3.3);
    });
  }
  if (stepInBar === 0 || stepInBar === 5) { // Kick.
    const osc = ctx.createOscillator(), gain = ctx.createGain();
    osc.frequency.setValueAtTime(110, when); osc.frequency.exponentialRampToValueAtTime(42, when + 0.14);
    gain.gain.setValueAtTime(0.5, when); gain.gain.exponentialRampToValueAtTime(0.001, when + 0.24);
    osc.connect(gain); gain.connect(out); osc.start(when); osc.stop(when + 0.25);
  }
  const hat = ctx.createBufferSource(), hatGain = ctx.createGain(), hatFilter = ctx.createBiquadFilter();
  hat.buffer = noise(ctx, 0.08); hatFilter.type = stepInBar === 2 || stepInBar === 6 ? "bandpass" : "highpass";
  hatFilter.frequency.value = stepInBar === 2 || stepInBar === 6 ? 1700 : 6500;
  hatGain.gain.setValueAtTime(stepInBar === 2 || stepInBar === 6 ? 0.2 : 0.05, when); hatGain.gain.exponentialRampToValueAtTime(0.001, when + 0.08);
  hat.connect(hatFilter); hatFilter.connect(hatGain); hatGain.connect(out); hat.start(when);
}

export function setMusic(on: boolean): void {
  const ctx = audio();
  if (!on) { window.clearInterval(timer); timer = 0; musicGain?.gain.linearRampToValueAtTime(0, ctx.currentTime + 0.4); return; }
  void ctx.resume();
  if (!musicGain) {
    musicGain = ctx.createGain(); musicGain.connect(ctx.destination);
    // Vinyl crackle underneath.
    const crackle = ctx.createBufferSource(), filter = ctx.createBiquadFilter(), gain = ctx.createGain();
    crackle.buffer = noise(ctx, 2); crackle.loop = true; filter.type = "bandpass"; filter.frequency.value = 2400; gain.gain.value = 0.02;
    crackle.connect(filter); filter.connect(gain); gain.connect(musicGain); crackle.start();
  }
  musicGain.gain.cancelScheduledValues(ctx.currentTime); musicGain.gain.linearRampToValueAtTime(0.5, ctx.currentTime + 0.6);
  nextBeat = ctx.currentTime + 0.1;
  const stepSeconds = 60 / 72 / 2;
  timer = window.setInterval(() => { while (nextBeat < ctx.currentTime + 0.3) { schedule(ctx, musicGain!, nextBeat + (beat % 2 ? 0.04 : 0), beat++); nextBeat += stepSeconds; } }, 100);
}

let effects = true;
export const setEffects = (on: boolean): void => { effects = on; };
export function blip(kind: "open" | "close" | "click" | "alert"): void {
  if (!effects) return;
  const ctx = audio(); void ctx.resume();
  const notes = kind === "open" ? [523, 784] : kind === "close" ? [659, 440] : kind === "alert" ? [880, 880, 1175] : [660];
  notes.forEach((frequency, i) => {
    const osc = ctx.createOscillator(), gain = ctx.createGain(), when = ctx.currentTime + i * 0.06;
    osc.type = "square"; osc.frequency.value = frequency;
    gain.gain.setValueAtTime(0.035, when); gain.gain.exponentialRampToValueAtTime(0.001, when + 0.09);
    osc.connect(gain); gain.connect(ctx.destination); osc.start(when); osc.stop(when + 0.1);
  });
}

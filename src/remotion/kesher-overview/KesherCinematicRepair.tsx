import React from "react";
import {AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig} from "remotion";
import {FullScreenSignatureOutro} from "../components/FullScreenSignatureOutro";

/**
 * Source-bound ORIGINAL illustrated film treatment.
 * No NotebookLM frame, invented stock footage, photo license, generative
 * likeness, or video duplication is used. Audio is added AFTER visual-only
 * rendering with ffmpeg -c:a copy from the exact original NotebookLM MP4.
 *
 * Storyboard (continuous motion, no title-card slideshow):
 * tension at the table → distance → unspoken fear → pause →
 * gentle approach → listening → reconnecting → shared calm.
 */
export type CinematicRepairProps = {
  durationInFrames: number;
  articleTitle: string;
  signatureImageSrc?: string;
};

const SCENES = [
  {start: 0, hue: "#5a4143", warm: "#b98562", gap: 0, reach: 0.12, face: 0.20, lamp: 0.44},
  {start: 11, hue: "#3e4450", warm: "#c08d65", gap: 45, reach: 0.76, face: 0.08, lamp: 0.32},
  {start: 23, hue: "#414d53", warm: "#d49a7b", gap: 85, reach: 0.04, face: 0.07, lamp: 0.26},
  {start: 35, hue: "#424953", warm: "#b58d73", gap: 110, reach: 0.01, face: 0.10, lamp: 0.20},
  {start: 47, hue: "#534d51", warm: "#d6a179", gap: 100, reach: 0.03, face: 0.13, lamp: 0.45},
  {start: 59, hue: "#5e5551", warm: "#e7b58a", gap: 65, reach: 0.13, face: 0.52, lamp: 0.59},
  {start: 71, hue: "#5b5960", warm: "#e4b58a", gap: 35, reach: 0.36, face: 0.83, lamp: 0.67},
  {start: 83, hue: "#596461", warm: "#ebc29d", gap: 15, reach: 0.61, face: 0.91, lamp: 0.74},
  {start: 95, hue: "#66716d", warm: "#f1cba3", gap: 0, reach: 0.79, face: 0.96, lamp: 0.83},
] as const;

const mix = (a: number, b: number, x: number) => a + (b - a) * x;
const smooth = (a: number, b: number, x: number) => {
  const t = Math.max(0, Math.min(1, (x - a) / (b - a)));
  return t * t * (3 - 2 * t);
};

function Person({x, y, scale, facing, shirt, skin, reach, breath, eye, armPhase}: {
  x: number; y: number; scale: number; facing: number;
  shirt: string; skin: string; reach: number; breath: number;
  eye: number; armPhase: number;
}) {
  const arm = 45 + reach * 42 + Math.sin(armPhase) * 3;
  return (
    <g transform={`translate(${x} ${y}) scale(${facing * scale} ${scale})`}>
      <ellipse cx="0" cy="168" rx="118" ry="20" fill="#191e25" opacity={0.17}/>
      <path d="M -89 176 Q -94 110 -51 72 Q 6 30 61 72 Q 107 110 95 176Z" fill={shirt}/>
      <path d="M -74 124 Q -82 96 -70 81 Q -31 55 -3 104" fill="none" stroke="#fff5e9" strokeWidth="7" opacity={0.13}/>
      <path d={`M -55 104 Q ${-30 + reach * 26} 136 ${arm} 113`} fill="none" stroke={skin} strokeWidth="31" strokeLinecap="round"/>
      <path d={`M ${arm - 13} 111 Q ${arm + 6} 104 ${arm + 20} 116`} fill="none" stroke={skin} strokeWidth="18" strokeLinecap="round"/>
      <rect x="-17" y="30" width="37" height="35" rx="15" fill={skin}/>
      <g transform={`translate(0 ${breath * 1.4})`}>
        <ellipse cx="1" cy="-8" rx="61" ry="77" fill={skin}/>
        <path d="M -59 -25 C -81 -120 47 -115 68 -41 Q 61 -78 32 -83 Q -2 -85 -30 -57 Z" fill="#312925"/>
        <path d="M -57 -16 Q -64 3 -60 17 Q -51 -34 -27 -57" fill="#312925"/>
        <circle cx={eye} cy="-8" r="4.2" fill="#342e2f"/>
        <path d="M 10 22 Q 22 25 35 20" fill="none" stroke="#6d4746" strokeWidth="3.5" strokeLinecap="round"/>
        <ellipse cx="-55" cy="3" rx="10" ry="15" fill={skin}/>
        <path d="M -38 44 Q 1 51 36 42" fill="none" stroke="#cc9078" strokeWidth="3" opacity="0.7"/>
      </g>
    </g>
  );
}

export const KesherCinematicRepair: React.FC<CinematicRepairProps> = ({
  durationInFrames, articleTitle, signatureImageSrc = "signature-mask.svg",
}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = Math.min(frame, Math.max(0, durationInFrames - 1)) / fps;
  const i = Math.min(SCENES.length - 1, SCENES.reduce(
    (n, scene, idx) => t >= scene.start ? idx : n, 0,
  ));
  const scene = SCENES[i];
  const next = SCENES[Math.min(i + 1, SCENES.length - 1)];
  const phase = t - scene.start;
  const duration = next.start - scene.start || 12;
  const blend = i === SCENES.length - 1 ? 0 : smooth(duration - 1.5, duration, phase);
  const gap = mix(scene.gap, next.gap, blend);
  const reach = mix(scene.reach, next.reach, blend);
  const face = mix(scene.face, next.face, blend);
  const lamp = mix(scene.lamp, next.lamp, blend);
  const breathing = Math.sin(t * 1.5);
  const cameraX = Math.sin(t * 0.043) * 13;
  const cameraY = Math.sin(t * 0.071) * 7;
  const cameraZoom = 1.025 + Math.sin(t * 0.057) * 0.022;
  const warm = blend > 0.5 ? next.warm : scene.warm;
  const wall = blend > 0.5 ? next.hue : scene.hue;
  const titleOpacity = interpolate(t, [0, 0.7, 4.2, 5.3], [0, 1, 1, 0], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });
  const minuteLight = Math.min(0.9, Math.max(0.32, lamp + 0.06 * Math.sin(t * 0.22)));

  return (
    <AbsoluteFill style={{overflow: "hidden", background: "#272c31"}}>
      <svg viewBox="0 0 1280 720" width="1280" height="720" style={{position:"absolute",inset:0}}>
        <defs>
          <linearGradient id="wall" x1="0" x2="1" y1="0" y2="1">
            <stop offset="0%" stopColor={wall}/>
            <stop offset="100%" stopColor="#1f3036"/>
          </linearGradient>
          <linearGradient id="floor" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#705d52"/>
            <stop offset="100%" stopColor="#3f3d3c"/>
          </linearGradient>
          <radialGradient id="glow">
            <stop offset="0%" stopColor={warm} stopOpacity={minuteLight}/>
            <stop offset="100%" stopColor={warm} stopOpacity="0"/>
          </radialGradient>
          <linearGradient id="glass" x1="0" x2="1" y1="0" y2="1">
            <stop offset="0%" stopColor="#b8bac0"/>
            <stop offset="100%" stopColor="#5e777c"/>
          </linearGradient>
          <filter id="soft"><feGaussianBlur stdDeviation="3"/></filter>
          <filter id="shadow"><feDropShadow dx="0" dy="18" stdDeviation="18" floodColor="#1a1d22" floodOpacity="0.36"/></filter>
        </defs>
        <g transform={`translate(${cameraX} ${cameraY}) translate(640 360) scale(${cameraZoom}) translate(-640 -360)`}>
          <rect width="1280" height="720" fill="url(#wall)"/>
          <circle cx="1060" cy="166" r="402" fill="url(#glow)"/>
          <path d="M 0 565 L 1280 550 L 1280 720 L 0 720Z" fill="url(#floor)"/>
          <path d="M 0 565 L 1280 550" stroke="#c29c7f" strokeWidth="6" opacity={0.5}/>
          <g filter="url(#shadow)">
            <rect x="72" y="83" width="345" height="320" rx="13" fill="#252d33"/>
            <rect x="87" y="98" width="313" height="288" fill="url(#glass)"/>
            <path d="M 243 98 L 243 386 M 87 242 L 400 242" stroke="#e4c9aa" strokeWidth="14"/>
            <path d="M 93 362 Q 164 320 235 343 T 399 314" fill="none" stroke="#cfbba4" strokeWidth="5" opacity={0.5}/>
          </g>
          <g opacity={0.84}>
            <ellipse cx="1115" cy="588" rx="65" ry="14" fill="#232a2c" opacity={0.35}/>
            <rect x="1095" y="440" width="42" height="145" rx="12" fill="#9f8d74"/>
            <path d="M 1113 447 Q 1030 420 1054 352 Q 1125 342 1113 447" fill="#5d8068"/>
            <path d="M 1113 430 Q 1196 378 1188 330 Q 1111 338 1113 430" fill="#70927a"/>
            <path d="M 1113 465 Q 1174 455 1192 400 Q 1118 383 1113 465" fill="#54785e"/>
            <path d="M 1113 411 Q 1063 343 1078 308 Q 1155 343 1113 411" fill="#466b57"/>
          </g>
          <path d="M 922 156 L 922 403" stroke="#b28e63" strokeWidth="9"/>
          <ellipse cx="923" cy="157" rx="93" ry="43" fill={warm} opacity={0.9}/>
          <circle cx="923" cy="152" r="185" fill="url(#glow)"/>
          <path d="M 895 409 L 950 409" stroke="#ad8d6e" strokeWidth="12" strokeLinecap="round"/>
          <g filter="url(#shadow)">
            <rect x="288" y="455" width="709" height="178" rx="62" fill="#9b786d"/>
            <rect x="288" y="450" width="703" height="39" rx="19" fill="#c2977c"/>
            <path d="M 330 492 L 326 632 M 950 489 L 955 629" stroke="#573d38" strokeWidth="22"/>
          </g>
          <g transform={`translate(${-gap / 2} 0)`}>
            <Person x={452} y={340} scale={1.06} facing={1}
              shirt="#456675" skin="#d6a087" reach={reach * 0.62}
              breath={breathing} eye={mix(30,38,face)} armPhase={t * 1.2}/>
          </g>
          <g transform={`translate(${gap / 2} 0)`}>
            <Person x={818} y={344} scale={1.02} facing={-1}
              shirt="#a77570" skin="#dba88e" reach={reach}
              breath={Math.sin(t * 1.4 + 0.5)} eye={mix(25,38,face)} armPhase={t * 1.1 + 0.7}/>
          </g>
          <g filter="url(#shadow)">
            <ellipse cx="634" cy="541" rx="180" ry="32" fill="#b88f70"/>
            <path d="M 471 530 Q 636 496 801 530 L 770 552 Q 639 580 498 553Z" fill="#6f4e3f"/>
            <ellipse cx="589" cy="520" rx="30" ry="16" fill="#f6e2ce"/>
            <rect x="566" y="488" width="48" height="33" rx="6" fill="#e8dac9"/>
            <path d="M 615 492 Q 642 489 639 505 Q 639 516 615 515" stroke="#e8dac9" strokeWidth="8" fill="none"/>
            <ellipse cx="706" cy="517" rx="29" ry="15" fill="#f6e2ce"/>
            <rect x="681" y="486" width="49" height="33" rx="6" fill="#d6d8c7"/>
            <path d="M 729 492 Q 756 492 753 507 Q 749 518 731 516" stroke="#d6d8c7" strokeWidth="8" fill="none"/>
          </g>
          <g opacity={0.14 + 0.07 * Math.sin(t * 0.34)}>
            <circle cx={195 + (t * 1.6) % 950} cy={240 + Math.sin(t * 0.34) * 80} r="14" fill="#fff1dc" filter="url(#soft)"/>
            <circle cx={270 + (t * 0.8) % 750} cy={320 + Math.cos(t * 0.24) * 55} r="9" fill="#f4d7b8" filter="url(#soft)"/>
          </g>
        </g>
      </svg>
      <AbsoluteFill style={{
        pointerEvents:"none",
        background:"linear-gradient(180deg,rgba(16,20,24,0.25),transparent 26%,transparent 72%,rgba(18,18,20,0.36))",
      }}/>
      <div dir="rtl" style={{
        position:"absolute", top:70, right:80, width:720, color:"#fff6e9",
        fontFamily:"Arial,sans-serif", fontSize:41, fontWeight:800, lineHeight:1.24,
        opacity:titleOpacity, textShadow:"0 4px 18px rgba(0,0,0,.85)",
      }}>{articleTitle}</div>
      <div style={{
        position:"absolute", left:62, bottom:30, color:"#fff0dc",
        fontFamily:"Arial,sans-serif", fontSize:19, fontWeight:650,
        textShadow:"0 2px 9px #292323",
      }}>kesher.saharoni.com</div>
      <FullScreenSignatureOutro durationSeconds={3} signatureImageSrc={signatureImageSrc}
        signatureColor="#d7aa79" websiteUrl="kesher.saharoni.com"/>
    </AbsoluteFill>
  );
};

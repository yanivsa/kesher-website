import React from 'react';
import {Video} from '@remotion/media';
import {AbsoluteFill, Easing, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';

export type KesherVideoProps = {
  videoSrc: string;
  title: string;
  hook: string;
  sourceDurationInFrames?: number;
  beatLabels?: string[];
  contentTheme?: 'mind-reading' | 'listening' | 'boundaries' | 'connection';
};

const theme = {ink: '#2f2521', cream: '#fff8f2', clay: '#b96345', rose: '#d9a08c', gold: '#f4c76c'};

export const KesherVideo = ({
  videoSrc,
  title,
  hook,
  beatLabels = ['לעצור', 'להקשיב', 'להתחבר'],
  contentTheme = 'connection',
}: KesherVideoProps) => {
  const frame = useCurrentFrame();
  const {fps, durationInFrames, width, height} = useVideoConfig();
  const seconds = frame / fps;
  const progress = frame / Math.max(durationInFrames - 1, 1);
  const isPortrait = height > width;
  const beat = Math.min(beatLabels.length - 1, Math.floor(progress * beatLabels.length));
  const beatPhase = (progress * beatLabels.length) % 1;
  const beatOpacity = interpolate(beatPhase, [0, 0.1, 0.82, 1], [0, 1, 1, 0], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(0.16, 1, 0.3, 1),
  });
  const introOpacity = interpolate(frame, [0, 0.4 * fps, 4.8 * fps, 5.4 * fps], [0, 1, 1, 0], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(0.16, 1, 0.3, 1),
  });
  const introY = interpolate(frame, [0, 0.7 * fps], [22, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const subtleZoom = interpolate(beatPhase, [0, 1], [1, 1.025], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const ctaPulse = interpolate(Math.sin(seconds * 2.2), [-1, 1], [0.98, 1.025]);
  const motifGlyph = { 'mind-reading': '?', listening: '◖◗', boundaries: '│', connection: '●—●'}[contentTheme];

  return (
    <AbsoluteFill style={{backgroundColor: theme.ink, overflow: 'hidden'}}>
      {isPortrait && (
        <Video src={staticFile(videoSrc)} muted objectFit="cover" style={{width: '100%', height: '100%', transform: 'scale(1.15)', filter: 'blur(28px) brightness(0.48) saturate(1.15)'}} />
      )}
      <Video
        src={staticFile(videoSrc)}
        objectFit={isPortrait ? 'contain' : 'cover'}
        style={{width: '100%', height: '100%', transform: `scale(${subtleZoom})`, filter: 'saturate(1.05) contrast(1.03)'}}
      />
      <AbsoluteFill style={{background: isPortrait
        ? 'linear-gradient(180deg, rgba(47,37,33,.38), rgba(47,37,33,.03) 28%, rgba(47,37,33,.03) 72%, rgba(47,37,33,.48))'
        : 'linear-gradient(180deg, rgba(47,37,33,.22), rgba(47,37,33,.02) 40%, rgba(47,37,33,.40))'}} />

      <div style={{position: 'absolute', top: isPortrait ? 54 : 36, left: isPortrait ? 34 : 46, right: isPortrait ? 34 : 46, height: 7, background: 'rgba(255,248,242,.35)', borderRadius: 999, overflow: 'hidden'}}>
        <div style={{width: `${Math.round(progress * 100)}%`, height: '100%', background: `linear-gradient(90deg, ${theme.gold}, ${theme.rose}, ${theme.clay})`}} />
      </div>

      <div dir="rtl" style={{position: 'absolute', top: isPortrait ? 88 : 76, ...(isPortrait ? {right: 34} : {left: 54}), maxWidth: isPortrait ? 520 : 680, opacity: beatOpacity, padding: isPortrait ? '13px 20px' : '10px 16px', borderRadius: 999, background: 'rgba(255,248,242,.92)', color: theme.ink, fontFamily: 'Arial, sans-serif', fontSize: isPortrait ? 27 : 24, fontWeight: 800, boxShadow: '0 10px 30px rgba(0,0,0,.18)'}}>
        {beatLabels[beat]}
      </div>

      <div aria-hidden style={{position: 'absolute', top: isPortrait ? 160 : 132, ...(isPortrait ? {left: 34} : {left: 62}), opacity: beatOpacity * 0.72, color: theme.gold, fontFamily: 'Arial, sans-serif', fontSize: isPortrait ? 38 : 32, fontWeight: 900, textShadow: '0 5px 20px rgba(0,0,0,.35)'}}>{motifGlyph}</div>

      {(title || hook) && (
        <div dir="rtl" style={{position: 'absolute', left: 78, right: 78, bottom: 130, opacity: introOpacity, transform: `translateY(${introY}px)`, fontFamily: 'Arial, sans-serif', color: theme.cream, textShadow: '0 8px 28px rgba(0,0,0,.45)'}}>
          <div style={{fontSize: 54, lineHeight: 1.06, fontWeight: 900}}>{hook}</div>
          <div style={{marginTop: 16, fontSize: 30, lineHeight: 1.18, fontWeight: 700}}>{title}</div>
        </div>
      )}

      <div dir="rtl" style={{position: 'absolute', right: isPortrait ? 30 : 38, bottom: isPortrait ? 42 : 38, transform: `scale(${ctaPulse})`, transformOrigin: 'bottom right', padding: isPortrait ? '12px 16px' : '8px 12px', width: isPortrait ? 248 : 204, borderRadius: 999, background: 'rgba(255,248,242,.9)', color: theme.ink, fontFamily: 'Arial, sans-serif', boxShadow: '0 16px 44px rgba(47,37,33,.32)', border: `2px solid ${theme.gold}`}}>
        <div style={{fontSize: isPortrait ? 19 : 16, fontWeight: 900}}>קשר | ייעוץ משפחתי</div>
        <div style={{fontSize: isPortrait ? 16 : 13, fontWeight: 800, color: theme.clay}}>kesher.saharoni.com</div>
      </div>

      <div style={{position: 'absolute', left: isPortrait ? 34 : 46, bottom: isPortrait ? 46 : 44, transform: `scale(${ctaPulse})`, transformOrigin: 'bottom left', padding: isPortrait ? '17px 23px' : '18px 27px', borderRadius: 999, background: 'rgba(255,248,242,.95)', color: theme.ink, fontFamily: 'Arial, sans-serif', fontSize: isPortrait ? 25 : 30, lineHeight: 1, letterSpacing: 0.2, fontWeight: 900, boxShadow: '0 18px 48px rgba(47,37,33,.36)', border: `4px solid ${theme.gold}`}}>kesher.saharoni.com</div>
    </AbsoluteFill>
  );
};

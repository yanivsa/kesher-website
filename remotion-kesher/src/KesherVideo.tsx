import React from 'react';
import {Video} from '@remotion/media';
import {AbsoluteFill, Easing, Img, interpolate, Sequence, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import type {ApprovedSourceIdentity, LicensedPhotoStory} from './licensedPhotoStory';
import {validateLicensedPhotoStory} from './licensedPhotoStory';

export type KesherVideoProps = {
  videoSrc: string;
  title: string;
  hook: string;
  sourceDurationInFrames?: number;
  beatLabels?: string[];
  contentTheme?: 'mind-reading' | 'listening' | 'boundaries' | 'connection';
  /** Explicit owner-approved source identity required for any photographic story. */
  sourceBinding?: ApprovedSourceIdentity;
  /** Optional licensed photographic B-roll. Absent by default; never infer approval. */
  licensedPhotoStory?: LicensedPhotoStory;
};

const theme = {ink: '#2f2521', cream: '#fff8f2', clay: '#b96345', rose: '#d9a08c', gold: '#f4c76c'};

export const KesherVideo = ({
  videoSrc,
  title,
  hook,
  beatLabels = ['לעצור', 'להקשיב', 'להתחבר'],
  contentTheme = 'connection',
  sourceBinding,
  licensedPhotoStory,
}: KesherVideoProps) => {
  const frame = useCurrentFrame();
  const {fps, durationInFrames, width, height} = useVideoConfig();
  const seconds = frame / fps;
  const progress = frame / Math.max(durationInFrames - 1, 1);
  const isPortrait = height > width;
  if (licensedPhotoStory) {
    if (isPortrait) throw new Error('PHOTO_STORY_OVERVIEW_ONLY');
    validateLicensedPhotoStory(licensedPhotoStory, sourceBinding, durationInFrames, fps);
  }
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
      {licensedPhotoStory && licensedPhotoStory.scenes.map((scene, index) => {
        const frameWithin = Math.max(0, frame - scene.startFrame);
        const sceneDuration = scene.endFrame - scene.startFrame;
        const cameraProgress = Math.min(1, frameWithin / Math.max(1, sceneDuration - 1));
        const scale = 1.045 + cameraProgress * 0.075;
        const drift = (index % 2 === 0 ? 1 : -1) * (cameraProgress - 0.5) * 30;
        return (
          <Sequence key={scene.assetPath} from={scene.startFrame} durationInFrames={sceneDuration}>
            <Img src={staticFile(scene.assetPath)} alt={scene.altHebrew}
              style={{
                width: '100%', height: '100%', objectFit: 'cover',
                transform: `scale(${scale}) translateX(${drift}px)`,
                filter: 'saturate(1.04) contrast(1.035)',
              }} />
          </Sequence>
        );
      })}
      <AbsoluteFill style={{background: isPortrait
        ? 'linear-gradient(180deg, rgba(47,37,33,.38), rgba(47,37,33,.03) 28%, rgba(47,37,33,.03) 72%, rgba(47,37,33,.48))'
        : 'linear-gradient(180deg, rgba(47,37,33,.22), rgba(47,37,33,.02) 40%, rgba(47,37,33,.40))'}} />

      <div style={{position: 'absolute', top: isPortrait ? 54 : 36, left: isPortrait ? 34 : 46, right: isPortrait ? 34 : 46, height: 7, background: 'rgba(255,248,242,.35)', borderRadius: 999, overflow: 'hidden'}}>
        <div style={{width: `${Math.round(progress * 100)}%`, height: '100%', background: `linear-gradient(90deg, ${theme.gold}, ${theme.rose}, ${theme.clay})`}} />
      </div>

      <div dir="rtl" style={{position: 'absolute', top: isPortrait ? 88 : 76, ...(isPortrait ? {right: 34} : {left: 54}), maxWidth: isPortrait ? 520 : 680, opacity: licensedPhotoStory ? 0 : beatOpacity, padding: isPortrait ? '13px 20px' : '10px 16px', borderRadius: 999, background: 'rgba(255,248,242,.92)', color: theme.ink, fontFamily: 'Arial, sans-serif', fontSize: isPortrait ? 27 : 24, fontWeight: 800, boxShadow: '0 10px 30px rgba(0,0,0,.18)'}}>
        {beatLabels[beat]}
      </div>

      <div aria-hidden style={{position: 'absolute', top: isPortrait ? 160 : 132, ...(isPortrait ? {left: 34} : {left: 62}), opacity: licensedPhotoStory ? 0 : beatOpacity * 0.72, color: theme.gold, fontFamily: 'Arial, sans-serif', fontSize: isPortrait ? 38 : 32, fontWeight: 900, textShadow: '0 5px 20px rgba(0,0,0,.35)'}}>{motifGlyph}</div>

      {(title || hook) && (
        <div dir="rtl" style={{position: 'absolute', left: 78, right: 78, bottom: 130, opacity: introOpacity, transform: `translateY(${introY}px)`, fontFamily: 'Arial, sans-serif', color: theme.cream, textShadow: '0 8px 28px rgba(0,0,0,.45)'}}>
          <div style={{fontSize: 54, lineHeight: 1.06, fontWeight: 900}}>{hook}</div>
          <div style={{marginTop: 16, fontSize: 30, lineHeight: 1.18, fontWeight: 700}}>{title}</div>
        </div>
      )}

      <div dir="rtl" style={{position: 'absolute', right: isPortrait ? 30 : 38, bottom: isPortrait ? 42 : 38, transform: `scale(${ctaPulse})`, transformOrigin: 'bottom right', padding: isPortrait ? '12px 16px' : (licensedPhotoStory ? '5px 9px' : '8px 12px'), width: isPortrait ? 248 : (licensedPhotoStory ? 180 : 204), borderRadius: 999, background: 'rgba(255,248,242,.9)', color: theme.ink, fontFamily: 'Arial, sans-serif', boxShadow: '0 16px 44px rgba(47,37,33,.32)', border: `2px solid ${theme.gold}`}}>
        <div style={{fontSize: isPortrait ? 19 : 16, fontWeight: 900}}>קשר | ייעוץ משפחתי</div>
        <div style={{fontSize: isPortrait ? 16 : 13, fontWeight: 800, color: theme.clay}}>kesher.saharoni.com</div>
      </div>

      <div style={{position: 'absolute', left: isPortrait ? 34 : 46, bottom: isPortrait ? 46 : 44, transform: `scale(${ctaPulse})`, transformOrigin: 'bottom left', display: licensedPhotoStory ? 'none' : undefined, padding: isPortrait ? '17px 23px' : '18px 27px', borderRadius: 999, background: 'rgba(255,248,242,.95)', color: theme.ink, fontFamily: 'Arial, sans-serif', fontSize: isPortrait ? 25 : 30, lineHeight: 1, letterSpacing: 0.2, fontWeight: 900, boxShadow: '0 18px 48px rgba(47,37,33,.36)', border: `4px solid ${theme.gold}`}}>kesher.saharoni.com</div>
    </AbsoluteFill>
  );
};

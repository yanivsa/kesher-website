import React from 'react';
import {Composition} from 'remotion';
import {KesherVideo, KesherVideoProps} from './KesherVideo';

const durationFromSource = ({props}: {props: KesherVideoProps}) => ({
  durationInFrames: props.sourceDurationInFrames ?? 4020,
});

export const RemotionRoot = () => {
  return (
    <>
      <Composition
        id="KesherVideo"
        component={KesherVideo}
        durationInFrames={4020}
        fps={30}
        width={1280}
        height={720}
        calculateMetadata={durationFromSource}
        defaultProps={{
          videoSrc: 'kesher-input.mp4',
          title: 'מה באמת קורה כשאנחנו מנסים לתקן?',
          hook: 'העזרה שלכם יכולה להישמע כמו ביקורת',
          sourceDurationInFrames: 4020,
          beatLabels: ['מה ציפיתי שיבינו?', 'לבקש במקום לנחש', 'ליצור שיחה ברורה'],
          contentTheme: 'mind-reading',
        }}
      />
      <Composition
        id="KesherShort"
        component={KesherVideo}
        durationInFrames={864}
        fps={24}
        width={720}
        height={1280}
        calculateMetadata={durationFromSource}
        defaultProps={{
          videoSrc: 'kesher-input.mp4',
          title: '',
          hook: '',
          sourceDurationInFrames: 864,
          beatLabels: ['לעצור', 'להקשיב', 'להתחבר'],
          contentTheme: 'listening',
        }}
      />
    </>
  );
};

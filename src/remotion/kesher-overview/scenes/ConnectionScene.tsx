import React from "react";
import {Easing, interpolate, useCurrentFrame, useVideoConfig} from "remotion";
import {VisualShell} from "../VisualShell";
import {palette} from "../theme";
import type {KesherSceneProps} from "../types";

export const ConnectionScene: React.FC<KesherSceneProps & {url: string}> = ({audience, url}) => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const progress = interpolate(frame, [0, durationInFrames * 0.72], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });
  const small = audience === "parenting" ? 0.82 : 1;
  const gap = interpolate(progress, [0, 1], [350, 125]);

  return (
    <VisualShell url={url}>
      <svg width="1280" height="720" viewBox="0 0 1280 720" style={{position: "absolute", inset: 0}}>
        <path d={`M${250 - gap / 4} 570 C280 80 560 80 640 365`} fill="none" stroke={palette.clay} strokeWidth="72" strokeLinecap="round" opacity={0.94} />
        <path d={`M${1030 + gap / 4} 570 C1000 ${110 + (1 - small) * 70} 720 80 640 365`} fill="none" stroke={palette.sage} strokeWidth={72 * small} strokeLinecap="round" opacity={0.94} />
        <circle cx="640" cy="365" r={70 + progress * 28} fill={palette.gold} opacity={0.9} />
        <circle cx="640" cy="365" r={34 + progress * 10} fill={palette.cream} />
      </svg>
      {[0, 1, 2].map((index) => (
        <div
          key={index}
          style={{
            position: "absolute",
            left: 578 + index * 58,
            top: 225 - index * 28,
            width: 26 + index * 9,
            height: 26 + index * 9,
            borderRadius: "55% 45% 55% 45%",
            background: index === 1 ? palette.rose : palette.gold,
            opacity: progress,
            rotate: `${frame / (8 + index * 3)}deg`,
          }}
        />
      ))}
    </VisualShell>
  );
};

import React from "react";
import {interpolate, useCurrentFrame, useVideoConfig} from "remotion";
import {VisualShell} from "../VisualShell";
import {palette} from "../theme";
import type {KesherSceneProps} from "../types";

export const DistanceScene: React.FC<KesherSceneProps & {url: string}> = ({audience, url}) => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const progress = interpolate(frame, [0, Math.max(1, durationInFrames - 1)], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const separation = interpolate(progress, [0, 0.55, 1], [180, 430, 350]);
  const scales = audience === "parenting" ? [1, 0.68] : [1, 1];

  return (
    <VisualShell url={url}>
      <svg width="1280" height="720" viewBox="0 0 1280 720" style={{position: "absolute", inset: 0}}>
        <path
          d="M535 -40 C760 150 490 280 725 430 C835 505 760 645 835 760"
          fill="none"
          stroke={palette.ink}
          strokeWidth="82"
          strokeLinecap="round"
          opacity="0.12"
        />
        <path
          d={`M${640 - separation / 2} 300 C520 ${175 + progress * 65} 760 ${520 - progress * 95} ${640 + separation / 2} 430`}
          fill="none"
          stroke={palette.rose}
          strokeWidth="9"
          strokeLinecap="round"
          strokeDasharray="18 22"
        />
      </svg>
      {[-1, 1].map((direction, index) => (
        <div
          key={direction}
          style={{
            position: "absolute",
            left: 640 + direction * separation / 2 - 70 * scales[index],
            top: (index === 0 ? 170 : 360) + (1 - scales[index]) * 65,
            width: 140 * scales[index],
            height: 240 * scales[index],
            borderRadius: "50% 50% 44% 44%",
            background: index === 0 ? palette.clay : palette.sage,
            rotate: `${direction * interpolate(progress, [0, 1], [0, 13])}deg`,
            boxShadow: "0 30px 70px rgba(54,39,32,.17)",
          }}
        />
      ))}
      {[0, 1, 2].map((index) => (
        <div
          key={index}
          style={{
            position: "absolute",
            left: 592 + index * 38,
            top: 335 - Math.sin(progress * Math.PI * 2 + index) * 62,
            width: 18,
            height: 18,
            borderRadius: "50%",
            background: palette.gold,
            opacity: interpolate(progress, [0, 0.2, 0.75, 1], [0, 1, 1, 0]),
          }}
        />
      ))}
    </VisualShell>
  );
};

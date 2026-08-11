import React from "react";
import {interpolate, useCurrentFrame, useVideoConfig} from "remotion";
import {VisualShell} from "../VisualShell";
import {palette} from "../theme";
import type {KesherSceneProps} from "../types";

export const DefenseScene: React.FC<KesherSceneProps & {url: string}> = ({audience, url}) => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const progress = frame / Math.max(1, durationInFrames - 1);
  const wall = interpolate(progress, [0, 0.42, 1], [0, 1, 0.48], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const small = audience === "parenting" ? 0.7 : 1;

  return (
    <VisualShell url={url}>
      <div style={{position: "absolute", left: 265, top: 250, width: 145, height: 245, borderRadius: "50% 50% 44% 44%", background: palette.clay}} />
      <div style={{position: "absolute", right: 265, top: 250 + (1 - small) * 70, width: 145 * small, height: 245 * small, borderRadius: "50% 50% 44% 44%", background: palette.sage}} />
      <div
        style={{
          position: "absolute",
          left: 565,
          top: 95 + (1 - wall) * 560,
          width: 150,
          height: 530,
          borderRadius: "46% 54% 42% 58%",
          background: `linear-gradient(90deg, ${palette.ink}, #5b4438)`,
          scale: `${0.78 + wall * 0.22} 1`,
          boxShadow: "0 25px 70px rgba(54,39,32,.24)",
        }}
      />
      <div
        style={{
          position: "absolute",
          left: 618,
          top: 290,
          width: 44,
          height: 140,
          borderRadius: 999,
          background: palette.gold,
          scale: `${1 - wall} 1`,
          opacity: 1 - wall * 0.65,
        }}
      />
    </VisualShell>
  );
};

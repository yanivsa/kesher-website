import React from "react";
import {interpolate, useCurrentFrame, useVideoConfig} from "remotion";
import {VisualShell} from "../VisualShell";
import {palette} from "../theme";
import type {KesherSceneProps} from "../types";

export const ConversationScene: React.FC<KesherSceneProps & {url: string}> = ({audience, url}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const pulse = (Math.sin(frame / fps * 3.2) + 1) / 2;
  const small = audience === "parenting" ? 0.76 : 1;

  return (
    <VisualShell url={url}>
      {[0, 1, 2].map((index) => (
        <React.Fragment key={index}>
          <div style={{position: "absolute", left: 215 - index * 34, top: 205 - index * 34, width: 220 + index * 68, height: 220 + index * 68, borderRadius: "50%", border: `5px solid ${palette.clay}`, opacity: 0.22 + pulse * 0.16}} />
          <div style={{position: "absolute", right: 215 - index * 34, top: 205 - index * 34, width: (220 + index * 68) * small, height: (220 + index * 68) * small, borderRadius: "50%", border: `5px solid ${palette.sage}`, opacity: 0.22 + (1 - pulse) * 0.16}} />
        </React.Fragment>
      ))}
      <div style={{position: "absolute", left: 285, top: 275, width: 80, height: 80, borderRadius: "50%", background: palette.clay, boxShadow: `0 0 70px ${palette.clay}66`}} />
      <div style={{position: "absolute", right: 285, top: 275 + (1 - small) * 40, width: 80 * small, height: 80 * small, borderRadius: "50%", background: palette.sage, boxShadow: `0 0 70px ${palette.sage}66`}} />
      {[0, 1, 2, 3].map((index) => {
        const opacity = interpolate((pulse + index * 0.22) % 1, [0, 0.35, 1], [0, 0.85, 0]);
        return (
          <div
            key={index}
            style={{
              position: "absolute",
            left: 510 + index * 66,
            top: 300 + Math.sin(frame / 13 + index) * 54,
              width: 30 + index * 3,
              height: 30 + index * 3,
              borderRadius: "50%",
              border: `7px solid ${index % 2 ? palette.sage : palette.clay}`,
              opacity,
            }}
          />
        );
      })}
      <svg width="620" height="220" viewBox="0 0 620 220" style={{position: "absolute", left: 330, top: 430}}>
        <path d="M10 135 C155 5 455 215 610 65" fill="none" stroke={palette.gold} strokeWidth="14" strokeLinecap="round" />
      </svg>
    </VisualShell>
  );
};

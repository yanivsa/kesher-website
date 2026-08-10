import React from "react";
import {Easing, interpolate, useCurrentFrame, useVideoConfig} from "remotion";
import {VisualShell} from "../VisualShell";
import {palette} from "../theme";
import type {KesherSceneProps} from "../types";

export const OpeningScene: React.FC<KesherSceneProps & {title: string; url: string}> = ({
  audience,
  title,
  url,
}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const reveal = interpolate(frame, [0, 1.2 * fps], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });
  const childScale = audience === "parenting" ? 0.72 : 1;

  return (
    <VisualShell url={url}>
      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: 180,
        }}
      >
        {[1, childScale].map((scale, index) => (
          <div
            key={index}
            style={{
              width: 150 * scale,
              height: 250 * scale,
              borderRadius: "48% 48% 42% 42%",
              background: index === 0 ? palette.clay : palette.sage,
              opacity: reveal,
              translate: `${(index === 0 ? -1 : 1) * (1 - reveal) * 90}px 0`,
              boxShadow: "0 26px 60px rgba(54,39,32,.16)",
            }}
          />
        ))}
      </div>
      <h1
        dir="rtl"
        style={{
          position: "absolute",
          left: 120,
          right: 120,
          top: 72,
          margin: 0,
          textAlign: "center",
          color: palette.ink,
          fontSize: 68,
          lineHeight: 1.08,
          fontWeight: 900,
          opacity: reveal,
          translate: `0 ${(1 - reveal) * 22}px`,
        }}
      >
        {title}
      </h1>
      <svg width="390" height="150" viewBox="0 0 390 150" style={{position: "absolute", left: 445, top: 390}}>
        <path
          d="M15 84 C105 5 280 145 375 65"
          fill="none"
          stroke={palette.gold}
          strokeWidth="12"
          strokeLinecap="round"
          pathLength="1"
          strokeDasharray="1"
          strokeDashoffset={1 - reveal}
        />
      </svg>
    </VisualShell>
  );
};

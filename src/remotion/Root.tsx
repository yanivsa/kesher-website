import React from "react";
import { Composition } from "remotion";
import { ArticleShort } from "./ArticleShort";
import type { ArticleShortProps } from "./ArticleShort";
import { KesherOverview } from "./kesher-overview/KesherOverview";
import type { KesherOverviewProps } from "./kesher-overview/types";

const SIGNATURE_OUTRO_SECONDS = 3;
const SHORT_FPS = 30;
const OVERVIEW_FPS = 30;
export const SHORT_SIGNATURE_OUTRO_FRAMES = SIGNATURE_OUTRO_SECONDS * SHORT_FPS;
export const OVERVIEW_SIGNATURE_OUTRO_FRAMES = SIGNATURE_OUTRO_SECONDS * OVERVIEW_FPS;

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition<ArticleShortProps>
        id="ArticleShort"
        component={ArticleShort}
        durationInFrames={1350 + SHORT_SIGNATURE_OUTRO_FRAMES}
        fps={SHORT_FPS}
        width={1080}
        height={1920}
        calculateMetadata={({props}) => ({
          durationInFrames: props.durationInFrames + SHORT_SIGNATURE_OUTRO_FRAMES,
        })}
        defaultProps={{
          videoSrc: "kesher-input.mp4",
          sourceStartFrame: 0,
          durationInFrames: 1350,
          title: "כותרת המאמר היומי",
          category: "זוגיות",
          url: "kesher.saharoni.com",
        }}
      />
      <Composition<KesherOverviewProps>
        id="KesherOverview"
        component={KesherOverview}
        durationInFrames={3120 + OVERVIEW_SIGNATURE_OUTRO_FRAMES}
        fps={OVERVIEW_FPS}
        width={1280}
        height={720}
        calculateMetadata={({props}) => ({
          durationInFrames: props.durationInFrames + OVERVIEW_SIGNATURE_OUTRO_FRAMES,
        })}
        defaultProps={{
          videoSrc: "kesher-input.mp4",
          audioSrc: "kesher-input.mp4",
          durationInFrames: 3120,
          title: "איך לדבר כשהלב סגור",
          category: "זוגיות",
          url: "kesher.saharoni.com",
        }}
      />
    </>
  );
};
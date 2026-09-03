import React from "react";
import { Composition } from "remotion";
import { ArticleShort } from "./ArticleShort";
import type { ArticleShortProps } from "./ArticleShort";
import { KesherOverview } from "./kesher-overview/KesherOverview";
import type { KesherOverviewProps } from "./kesher-overview/types";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition<ArticleShortProps>
        id="ArticleShort"
        component={ArticleShort}
        durationInFrames={1350}
        fps={30}
        width={1080}
        height={1920}
        calculateMetadata={({props}) => ({durationInFrames: props.durationInFrames})}
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
        durationInFrames={3120}
        fps={30}
        width={1280}
        height={720}
        calculateMetadata={({props}) => ({durationInFrames: props.durationInFrames})}
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

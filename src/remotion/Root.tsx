import React from "react";
import { Composition } from "remotion";
import { ArticleShort } from "./ArticleShort";
import type { ArticleShortProps } from "./ArticleShort.types";
import { KesherOverview } from "./kesher-overview/KesherOverview";
import { KesherCinematicRepair } from "./kesher-overview/KesherCinematicRepair";
import type { CinematicRepairProps } from "./kesher-overview/KesherCinematicRepair";
import type { KesherOverviewProps } from "./kesher-overview/types";

const SHORT_FPS = 30;
const OVERVIEW_FPS = 30;

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition<ArticleShortProps>
        id="ArticleShort"
        component={ArticleShort}
        durationInFrames={1350}
        fps={SHORT_FPS}
        width={1080}
        height={1920}
        calculateMetadata={({props}) => ({
          durationInFrames: props.durationInFrames,
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
      <Composition<CinematicRepairProps>
        id="KesherCinematicRepair"
        component={KesherCinematicRepair}
        durationInFrames={3240}
        fps={30}
        width={1280}
        height={720}
        calculateMetadata={({props}) => ({durationInFrames: props.durationInFrames})}
        defaultProps={{
          durationInFrames: 3240,
          articleTitle: "למה כל שיחה בינינו נתקעת — ואיך יוצאים ממעגל הרדיפה וההתרחקות?",
          signatureImageSrc: "signature-mask.svg",
        }}
      />
      <Composition<KesherOverviewProps>
        id="KesherOverview"
        component={KesherOverview}
        durationInFrames={3120}
        fps={OVERVIEW_FPS}
        width={1280}
        height={720}
        calculateMetadata={({props}) => ({
          durationInFrames: props.durationInFrames,
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

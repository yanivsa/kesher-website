import React from "react";
import {Audio} from "@remotion/media";
import {fade} from "@remotion/transitions/fade";
import {linearTiming} from "@remotion/transitions";
import {TransitionSeries} from "@remotion/transitions";
import {staticFile, useVideoConfig} from "remotion";
import {ConnectionScene} from "./scenes/ConnectionScene";
import {ConversationScene} from "./scenes/ConversationScene";
import {DefenseScene} from "./scenes/DefenseScene";
import {DistanceScene} from "./scenes/DistanceScene";
import {OpeningScene} from "./scenes/OpeningScene";
import type {KesherOverviewProps} from "./types";

export const KesherOverview: React.FC<KesherOverviewProps> = ({
  audioSrc,
  title,
  category,
  url,
}) => {
  const {durationInFrames, fps} = useVideoConfig();
  const transitionFrames = Math.round(0.8 * fps);
  const sceneFrames = Math.ceil((durationInFrames + transitionFrames * 4) / 5);
  const audience = category.includes("הור") || category.includes("ילד") ? "parenting" : "couples";
  const transition = (
    <TransitionSeries.Transition
      presentation={fade()}
      timing={linearTiming({durationInFrames: transitionFrames})}
    />
  );

  return (
    <>
      <Audio src={staticFile(audioSrc)} />
      <TransitionSeries>
        <TransitionSeries.Sequence durationInFrames={sceneFrames} name="פתיחה">
          <OpeningScene audience={audience} title={title} url={url} />
        </TransitionSeries.Sequence>
        {transition}
        <TransitionSeries.Sequence durationInFrames={sceneFrames} name="ריחוק">
          <DistanceScene audience={audience} url={url} />
        </TransitionSeries.Sequence>
        {transition}
        <TransitionSeries.Sequence durationInFrames={sceneFrames} name="הגנה">
          <DefenseScene audience={audience} url={url} />
        </TransitionSeries.Sequence>
        {transition}
        <TransitionSeries.Sequence durationInFrames={sceneFrames} name="שיחה">
          <ConversationScene audience={audience} url={url} />
        </TransitionSeries.Sequence>
        {transition}
        <TransitionSeries.Sequence durationInFrames={sceneFrames} name="חיבור">
          <ConnectionScene audience={audience} url={url} />
        </TransitionSeries.Sequence>
      </TransitionSeries>
    </>
  );
};

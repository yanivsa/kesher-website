export interface MotionTarget {
  startFrame: number;
  endFrame: number;
  focusX: number;
  focusY: number;
  zoom: number;
  rotation: number;
  assetRef?: string;
  assetType?: "image" | "broll" | "motion_graphic";
  assetStartFrame?: number;
  assetEndFrame?: number;
  assetIntent?: string;
  assetProvenance?: string;
}

export const SHORT_GEOMETRY = {
  width: 1080,
  height: 1920,
  baseScale: 1.11, // ~90% framing / ~10% crop
  safeArea: {
    top: 180, // Upper safe area
    bottom: 600, // Reserved for captions
    left: 40,
    right: 120, // Right side controls
  }
};

export interface ArticleShortProps {
  videoSrc: string;
  sourceStartFrame: number;
  durationInFrames: number;
  title: string;
  category: string;
  url: string;
  signatureImageSrc?: string;
  motionPlan?: MotionTarget[];
}

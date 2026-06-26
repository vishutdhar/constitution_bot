import { Composition, type CalculateMetadataFunction } from "remotion";
import { ConstitutionDay, type DayProps } from "./Composition";
import days from "../data/days.json";

const FPS = 30;
const WIDTH = 1080;
const HEIGHT = 1920;

// Default to Day 1 so Studio opens to a real, fully-populated composition.
const DEFAULT_DAY = (days as DayProps[])[0];

// Duration is per-day: each day's narration has a different length, baked into
// data/days.json (durationInFrames = ceil(audioSeconds * fps) + tail).
const calculateMetadata: CalculateMetadataFunction<DayProps> = ({ props }) => ({
  durationInFrames: props.durationInFrames,
  fps: FPS,
  width: WIDTH,
  height: HEIGHT,
});

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="ConstitutionDay"
      component={ConstitutionDay}
      durationInFrames={DEFAULT_DAY.durationInFrames}
      fps={FPS}
      width={WIDTH}
      height={HEIGHT}
      defaultProps={DEFAULT_DAY}
      calculateMetadata={calculateMetadata}
    />
  );
};

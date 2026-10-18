import ageThreePottyTraining from './p1/potty-training-age-3-problems.json';
import nighttimePottyTraining from './p1/nighttime-potty-training.json';
import pottyTrainingRegression from './p1/potty-training-regression.json';
import firstGradePreparation from './p1/prepare-for-first-grade.json';
import firstGradeReadiness from './p1/first-grade-readiness.json';

const p1Posts = [
  ...ageThreePottyTraining,
  ...nighttimePottyTraining,
  ...pottyTrainingRegression,
  ...firstGradePreparation,
  ...firstGradeReadiness,
];

export default p1Posts;

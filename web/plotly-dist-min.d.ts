declare module "plotly.js-dist-min";
declare module "react-plotly.js/factory" {
  import type { PlotParams } from "react-plotly.js";
  import type * as React from "react";
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  export default function createPlotlyComponent(plotly: any): React.ComponentType<PlotParams>;
}

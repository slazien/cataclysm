import * as d3 from "d3";
import { chartTheme } from "./theme";

export function distanceScale(domain: [number, number], range: [number, number]) {
  return d3.scaleLinear().domain(domain).range(range);
}

export function speedScale(domain: [number, number], range: [number, number]) {
  return d3.scaleLinear().domain(domain).range(range);
}

export function lapColorScale(lapNumbers: number[]) {
  return d3
    .scaleOrdinal<number, string>()
    .domain(lapNumbers)
    .range(chartTheme.lapColors);
}

export function deltaColorScale() {
  return (value: number) => (value <= 0 ? chartTheme.accentGreen : chartTheme.accentRed);
}

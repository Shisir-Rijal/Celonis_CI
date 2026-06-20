/**
 * Placeholder data for the branding agent's color interpretation.
 *
 * Replace this entire module (or just the export below) once the agent is
 * live — `hooks.ts` is the only file that needs to change to point at the
 * real endpoint instead.
 */

import type { ColorInsights } from "./types";

export const DUMMY_COLOR_INSIGHTS: ColorInsights = {
  spectrum: [
    {
      colorFamily: "Blue",
      representativeHex: "#1A73E8",
      usageLabel: "Very common",
      usageCount: 6,
      usedBy: [
        { company: "IBM", hex: "#0F62FE", colorType: "primary" },
        { company: "Microsoft Fabric", hex: "#0078D4", colorType: "primary" },
        { company: "Signavio", hex: "#1A73E8", colorType: "primary" },
        { company: "Apromore", hex: "#2563EB", colorType: "primary" },
        { company: "ARIS", hex: "#1E40AF", colorType: "primary" },
        { company: "Palantir", hex: "#0B1F3A", colorType: "primary" },
      ],
      association:
        "Trust, stability, and enterprise reliability — the default choice for B2B software and the most crowded part of the spectrum.",
    },
    {
      colorFamily: "Red / Orange",
      representativeHex: "#FA4616",
      usageLabel: "Common",
      usageCount: 3,
      usedBy: [
        { company: "Databricks", hex: "#FF3621", colorType: "primary" },
        { company: "UiPath", hex: "#FA4616", colorType: "primary" },
        { company: "Appian", hex: "#C8102E", colorType: "primary" },
      ],
      association:
        "Energy, urgency, and disruption — common among challenger brands positioning against legacy incumbents.",
    },
    {
      colorFamily: "Green",
      representativeHex: "#5CFE50",
      usageLabel: "Common",
      usageCount: 2,
      usedBy: [
        { company: "Celonis", hex: "#5CFE50", colorType: "primary" },
        { company: "ServiceNow", hex: "#81B5A1", colorType: "secondary" },
      ],
      association:
        "Growth, automation, and forward motion — also reads as 'go' / efficiency signaling, which fits process-mining and workflow brands well.",
    },
    {
      colorFamily: "Black / Neutral",
      representativeHex: "#111111",
      usageLabel: "Occasional",
      usageCount: 2,
      usedBy: [
        { company: "OpenAI", hex: "#0D0D0D", colorType: "primary" },
        { company: "Anthropic", hex: "#191919", colorType: "primary" },
      ],
      association:
        "Minimalism and seriousness — both leading AI-model labs converge on near-black, letting a single accent color carry the brand instead.",
    },
    {
      colorFamily: "Terracotta / Warm Beige",
      representativeHex: "#D97757",
      usageLabel: "Rare",
      usageCount: 1,
      usedBy: [{ company: "Anthropic", hex: "#D97757", colorType: "secondary" }],
      association:
        "Warmth and approachability — a deliberate break from the cold blues/greys typical of AI branding.",
    },
    {
      colorFamily: "Purple",
      representativeHex: "#7C3AED",
      usageLabel: "Rare",
      usageCount: 0,
      usedBy: [],
      association:
        "Not used by any tracked competitor right now — purple reads as creative/premium and is genuine whitespace in this set.",
    },
    {
      colorFamily: "Yellow / Gold",
      representativeHex: "#F2C94C",
      usageLabel: "Rare",
      usageCount: 0,
      usedBy: [],
      association:
        "Also unclaimed — high attention-grabbing value, but riskier for an enterprise-software context (can read as caution/cheap if overused).",
    },
  ],
  diversity: [
    {
      company: "Microsoft Fabric",
      hues: [
        { hueFamily: "Blue", colors: ["#0078D4", "#50E6FF"] },
        { hueFamily: "Yellow / Gold", colors: ["#FFB900"] },
        { hueFamily: "Purple", colors: ["#742774"] },
        { hueFamily: "Green", colors: ["#107C10"] },
      ],
    },
    {
      company: "Databricks",
      hues: [
        { hueFamily: "Red / Orange", colors: ["#FF3621"] },
        { hueFamily: "Blue", colors: ["#1B3139"] },
        { hueFamily: "Black / Neutral", colors: ["#FFFFFF"] },
        { hueFamily: "Green", colors: ["#00A972"] },
      ],
    },
    {
      company: "UiPath",
      hues: [
        { hueFamily: "Red / Orange", colors: ["#FA4616"] },
        { hueFamily: "Black / Neutral", colors: ["#1B1B1B", "#FFFFFF"] },
        { hueFamily: "Yellow / Gold", colors: ["#FFB81C"] },
      ],
    },
    {
      company: "Celonis",
      hues: [
        { hueFamily: "Green", colors: ["#5CFE50"] },
        { hueFamily: "Black / Neutral", colors: ["#0A0A0A", "#FFFFFF"] },
      ],
    },
    {
      company: "ServiceNow",
      hues: [
        { hueFamily: "Green", colors: ["#81B5A1"] },
        { hueFamily: "Black / Neutral", colors: ["#03150F", "#FFFFFF"] },
      ],
    },
    {
      company: "IBM",
      hues: [
        { hueFamily: "Blue", colors: ["#0F62FE"] },
        { hueFamily: "Black / Neutral", colors: ["#161616"] },
      ],
    },
    {
      company: "Appian",
      hues: [
        { hueFamily: "Red / Orange", colors: ["#C8102E"] },
        { hueFamily: "Black / Neutral", colors: ["#1A1A1A"] },
      ],
    },
    {
      company: "Signavio",
      hues: [
        { hueFamily: "Blue", colors: ["#1A73E8"] },
        { hueFamily: "Black / Neutral", colors: ["#FFFFFF"] },
      ],
    },
    {
      company: "Apromore",
      hues: [
        { hueFamily: "Blue", colors: ["#2563EB"] },
        { hueFamily: "Black / Neutral", colors: ["#0F172A"] },
      ],
    },
    {
      company: "ARIS",
      hues: [
        { hueFamily: "Blue", colors: ["#1E40AF"] },
        { hueFamily: "Black / Neutral", colors: ["#F5F5F5"] },
      ],
    },
    {
      company: "Anthropic",
      hues: [
        { hueFamily: "Black / Neutral", colors: ["#191919"] },
        { hueFamily: "Terracotta / Warm Beige", colors: ["#D97757"] },
      ],
    },
    { company: "Palantir", hues: [{ hueFamily: "Blue", colors: ["#0B1F3A"] }] },
    { company: "OpenAI", hues: [{ hueFamily: "Black / Neutral", colors: ["#0D0D0D"] }] },
  ],
  warmCoolSplit: {
    warmPct: 31,
    coolPct: 54,
    neutralPct: 15,
    warmCompanies: ["Databricks", "UiPath", "Appian", "Anthropic"],
    coolCompanies: [
      "Celonis",
      "IBM",
      "Microsoft Fabric",
      "Signavio",
      "Apromore",
      "ARIS",
      "ServiceNow",
    ],
    neutralCompanies: ["OpenAI", "Palantir"],
  },
  generatedAt: null,
};

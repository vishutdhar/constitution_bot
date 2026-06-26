/**
 * CLI / Studio config. Note: the Node SSR APIs (scripts/render-all.mjs) do NOT
 * read this file — options are passed directly to renderMedia() there.
 */
import { Config } from "@remotion/cli/config";

Config.setVideoImageFormat("jpeg");
Config.setOverwriteOutput(true);

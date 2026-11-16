import { Config } from "@remotion/cli/config";

// 2-core GitHub runners: software WebGL (SwiftShader via ANGLE) so three.js and shaders render without a GPU.
Config.setChromiumOpenGlRenderer("swangle");
Config.setConcurrency(2);
Config.setVideoImageFormat("jpeg");

import type { ShortestConfig } from "@antiwork/shortest";

export default {
  headless: false,
  baseUrl: "https://rbbrier.eco-serv.jp/etc/mypage/",
  testPattern: "**/*.test.ts",
  anthropicKey: process.env.ANTHROPIC_API_KEY,
} satisfies ShortestConfig;

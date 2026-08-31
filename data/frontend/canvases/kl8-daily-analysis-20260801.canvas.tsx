import {
  BarChart,
  Callout,
  Card,
  CardBody,
  CardHeader,
  Divider,
  Grid,
  H1,
  H2,
  H3,
  Pill,
  Row,
  Stack,
  Stat,
  Table,
  Text,
} from "cursor/canvas";

const HE5_HISTORY = [
  { period: "2026193", hits: 2, lift: 1.6 },
  { period: "2026194", hits: 2, lift: 1.6 },
  { period: "2026195", hits: 2, lift: 1.6 },
  { period: "2026196", hits: 1, lift: 0.8 },
  { period: "2026197", hits: 3, lift: 2.4 },
  { period: "2026198", hits: 2, lift: 1.6 },
  { period: "2026199", hits: 1, lift: 0.8 },
  { period: "2026200", hits: 2, lift: 1.6 },
  { period: "2026201", hits: 0, lift: 0.0 },
  { period: "2026202", hits: 2, lift: 1.6 },
];

const CHANNELS = [
  ["HE5", "04 12 17 32 42"],
  ["Trinity5", "12 32 41 42 43"],
  ["Trinity12", "02 04 08 12 27 32 41 42 43 45 71 73"],
  ["AI5", "33 04 25 32 57"],
  ["AI12", "33 04 25 32 57 60 12 17 29 40 42 44"],
  ["Golden", "02 04 12 27 32 42"],
  ["mRMR", "12 75 17 66 42 29 69 18 27 61 02 10"],
  ["纯净池高置信", "53 06 29"],
  ["纯净池旧规则", "53 29"],
  ["纯净池LR", "53 06 29"],
  ["纯净池全量", "06 29 44 53"],
  ["爆发Top5", "24 21 73 70 71"],
  ["防守Top3", "46 07 01"],
];

export default function DailyAnalysis20260801() {
  return (
    <Stack gap={20}>
      <Stack gap={6}>
        <H1>快乐8 每日分析 · 目标期 2026203</H1>
        <Text tone="secondary">
          2026-08-01 · kl8最新 2026202 · 六项校验 PASS · v4.2
        </Text>
      </Stack>

      <Grid columns={4} gap={12}>
        <Stat value="04 12 17 32 42" label="HE5 主推" />
        <Stat value="1.36x" label="HE5近10期均值Lift" />
        <Stat value="FROZEN" label="自学习门控" tone="warning" />
        <Stat value="无需调整" label="优化决策" tone="success" />
      </Grid>

      <Callout tone="info" title="上期复盘 2026202">
        learner Top5 1/5 (0.80x) · HE5 2/5 (1.60x，推荐 02 17 27 45 65) ·
        开奖含 01 04 07 10 12 15 16 17 26 29 32 40 42 44 49 65 68 73 77 78
      </Callout>

      <H2>HE5 近窗 Lift</H2>
      <BarChart
        categories={HE5_HISTORY.map((r) => r.period)}
        series={[
          {
            name: "HE5 Lift",
            data: HE5_HISTORY.map((r) => r.lift),
            tone: "accent",
          },
        ]}
        height={220}
      />
      <Text tone="secondary" size="small">
        随机基线=1.0x · WF≈1.0046 未达解锁阈值1.1 · KL Z=0.00σ
      </Text>

      <H2>今日主推</H2>
      <Card>
        <CardHeader
          title="Hidden Energy 5"
          trailing={
            <Pill tone="success" active>
              主通道
            </Pill>
          }
        />
        <CardBody>
          <H3>04 12 17 32 42</H3>
          <Text tone="secondary">
            Trinity 12 32 41 42 43 · AI 33 04 25 32 57 · 爆发 24 21 73 70 71 ·
            防守杀号 46 07 01
          </Text>
        </CardBody>
      </Card>

      <Table headers={["通道", "号码"]} rows={CHANNELS} />

      <Divider />
      <Row gap={8} wrap>
        <Pill>平衡震荡期</Pill>
        <Pill>信标 Level1×0.5</Pill>
        <Pill tone="warning">WF FROZEN</Pill>
        <Pill tone="success">v4.2 维持</Pill>
      </Row>
    </Stack>
  );
}

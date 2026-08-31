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

const PERIODS = [
  {
    date: "2026-07-25",
    target: "2026196",
    review: "2026195",
    top5: "1/5",
    lift5: 0.8,
    top12: "3/12",
    lift12: 1.0,
    he5: "19 30 40 46 47",
    trinity5: "15 30 40 46 50",
    ai5: "19 37 40 47 52",
    golden: "15 27 30 46 51 75",
    burst: "30 27 12 49 42",
    defense: "29 23 80",
  },
  {
    date: "2026-07-26",
    target: "2026197",
    review: "2026196",
    top5: "1/5",
    lift5: 0.8,
    top12: "2/12",
    lift12: 0.67,
    he5: "06 39 40 42 50",
    trinity5: "30 39 40 42 71",
    ai5: "14 39 40 03 06",
    golden: "06 15 40 42 46 75",
    burst: "30 27 12 42 49",
    defense: "29 23 80",
  },
  {
    date: "2026-07-27",
    target: "2026198",
    review: "2026197",
    top5: "3/5",
    lift5: 2.4,
    top12: "5/12",
    lift12: 1.67,
    he5: "06 12 39 42 75",
    trinity5: "39 40 42 71 75",
    ai5: "06 19 24 30 31",
    golden: "06 12 39 40 42 46 53 71 75",
    burst: "27 30 12 42 49",
    defense: "29 23 80",
  },
  {
    date: "2026-07-28",
    target: "2026199",
    review: "2026198",
    top5: "2/5",
    lift5: 1.6,
    top12: "5/12",
    lift12: 1.67,
    he5: "19 42 50 74 75",
    trinity5: "42 50 52 53 75",
    ai5: "68 19 43 56 31",
    golden: "06 19 27 39 40 42 53 75",
    burst: "27 12 06 53 65",
    defense: "46 24 55",
  },
];

const TODAY = {
  he5: "19 42 50 74 75",
  trinity5: "42 50 52 53 75",
  trinity12: "06 19 27 39 40 42 50 52 53 56 71 75",
  ai5: "68 19 43 56 31",
  ai12: "68 19 43 56 31 01 14 42 73 74 75 79",
  golden: "06 19 27 39 40 42 53 75",
  mrmr: "12 39 75 42 30 18 69 10 27 19 06 46",
  pureHigh: "01 15 02",
  pureOld: "01 15 02 53 42 73 51",
  pureLr: "01 15 02",
  pureAll: "01 02 06 10 15 27 42 46 51 53 71 73",
  burst: "27 12 06 53 65",
  defense: "46 24 55",
  consensus: "27 40",
};

export default function CatchupDailyAnalysis() {
  return (
    <Stack gap={20}>
      <Stack gap={6}>
        <H1>快乐8 断档4期回补 · 2026196→2026199</H1>
        <Text tone="secondary">
          Source: catchup pipeline · 2026-07-28 · kl8最新 2026198 · 目标预测
          2026199 · v4.2
        </Text>
      </Stack>

      <Grid columns={4} gap={12}>
        <Stat value="4/4" label="断档期已补跑" tone="success" />
        <Stat value="1.40x" label="4期 Top5 均值 Lift" />
        <Stat value="FROZEN" label="自学习门控" tone="warning" />
        <Stat value="无需调整" label="优化决策" tone="success" />
      </Grid>

      <Callout tone="info" title="问题与修复">
        kl8 滞后4期已抓取；跟随表缺 2026196–2026198
        已补同步；报告支持 KL8_REPORT_DATE
        回补写日；DataCenter 缺目标期 data1 时先 sync 热码。
      </Callout>

      <H2>复盘命中（learner Top5 / Top12）</H2>
      <BarChart
        categories={PERIODS.map((p) => p.review)}
        series={[
          {
            name: "Top5 Lift",
            data: PERIODS.map((p) => p.lift5),
            tone: "accent",
          },
          {
            name: "Top12 Lift",
            data: PERIODS.map((p) => p.lift12),
            tone: "info",
          },
        ]}
        height={220}
      />
      <Text tone="secondary" size="small">
        随机基线 Lift=1.0x · 门控解锁阈值 WF&gt;1.1 · 当前 WF≈1.0043 仍冻结
      </Text>

      <Table
        headers={[
          "日期",
          "目标期",
          "复盘期",
          "Top5",
          "Lift5",
          "Top12",
          "Lift12",
        ]}
        rows={PERIODS.map((p) => [
          p.date,
          p.target,
          p.review,
          p.top5,
          p.lift5.toFixed(2) + "x",
          p.top12,
          p.lift12.toFixed(2) + "x",
        ])}
      />

      <H2>今日主推 · 2026199</H2>
      <Card>
        <CardHeader
          title="Hidden Energy 5"
          trailing={<Pill tone="success" active>主通道</Pill>}
        />
        <CardBody>
          <H3>{TODAY.he5}</H3>
          <Text tone="secondary">
            Trinity {TODAY.trinity5} · AI {TODAY.ai5} · 爆发 {TODAY.burst} ·
            防守杀号 {TODAY.defense}
          </Text>
        </CardBody>
      </Card>

      <Table
        headers={["通道", "号码"]}
        rows={[
          ["HE5", TODAY.he5],
          ["Trinity5", TODAY.trinity5],
          ["Trinity12", TODAY.trinity12],
          ["AI5", TODAY.ai5],
          ["AI12", TODAY.ai12],
          ["Golden", TODAY.golden],
          ["mRMR", TODAY.mrmr],
          ["纯净池高置信", TODAY.pureHigh],
          ["纯净池旧规则", TODAY.pureOld],
          ["纯净池LR", TODAY.pureLr],
          ["纯净池全量", TODAY.pureAll],
          ["爆发Top5", TODAY.burst],
          ["防守Top3", TODAY.defense],
          ["跨规则共识", TODAY.consensus],
        ]}
      />

      <Divider />
      <H2>四期 HE5 推荐一览</H2>
      <Table
        headers={["目标期", "HE5", "Trinity5", "AI5", "爆发", "防守"]}
        rows={PERIODS.map((p) => [
          p.target,
          p.he5,
          p.trinity5,
          p.ai5,
          p.burst,
          p.defense,
        ])}
      />

      <Row gap={8} wrap>
        <Pill>六项校验 PASS</Pill>
        <Pill>KL Z≈3.0σ 未熔断</Pill>
        <Pill tone="warning">WF FROZEN</Pill>
        <Pill tone="success">v4.2 维持</Pill>
      </Row>
    </Stack>
  );
}

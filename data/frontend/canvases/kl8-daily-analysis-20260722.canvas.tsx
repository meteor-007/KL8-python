import {
  BarChart,
  Callout,
  Card,
  CardBody,
  CardHeader,
  Divider,
  Grid,
  H1,
  LineChart,
  Pill,
  Row,
  Spacer,
  Stack,
  Stat,
  Table,
  Text,
} from "cursor/canvas";

const HIT_TREND = [
  { period: "183", HE5: 2, Tr5: 2, AI5: 1 },
  { period: "184", HE5: 1, Tr5: 0, AI5: 1 },
  { period: "185", HE5: 0, Tr5: 1, AI5: 1 },
  { period: "186", HE5: 1, Tr5: 3, AI5: 2 },
  { period: "187", HE5: 3, Tr5: 2, AI5: 1 },
  { period: "188", HE5: 2, Tr5: 1, AI5: 1 },
  { period: "189", HE5: 2, Tr5: 2, AI5: 1 },
  { period: "190", HE5: 0, Tr5: 0, AI5: 0 },
  { period: "191", HE5: 1, Tr5: 0, AI5: 2 },
  { period: "192", HE5: 3, Tr5: 0, AI5: 2 },
];

const MODULE_LIFT = [
  { label: "HE5", lift: 1.2 },
  { label: "Tr5", lift: 0.88 },
  { label: "Tr12", lift: 0.97 },
  { label: "AI5", lift: 0.96 },
  { label: "AI12", lift: 0.97 },
];

const RECS = [
  { channel: "HE5", picks: "46 15 32 12 75", note: "评分序 · 首席主通道" },
  { channel: "Trinity5", picks: "29 33 47 53 71", note: "EF0.50 RW0.20 FO0.30" },
  { channel: "Trinity12", picks: "06 11 12 17 23 29 33 46 47 52 53 71", note: "三维融合" },
  { channel: "AI5", picks: "08 28 32 46 51", note: "置信度精选" },
  { channel: "AI12", picks: "08 28 32 46 51 75 20 56 10 15 44 59", note: "综合拦截" },
  { channel: "Golden", picks: "06 11 12 23 46", note: "多维共振" },
  { channel: "mRMR", picks: "12 33 39 77 69 30 27 18 10 42 11 61", note: "熵控筛选" },
  { channel: "纯净池高置信", picks: "33 53 77", note: "LR软回退主输出" },
  { channel: "纯净池旧规则", picks: "33 01 69", note: "评分>=3" },
  { channel: "纯净池LR", picks: "33 53 77", note: "影子候选" },
  { channel: "纯净池全量", picks: "33 53 77 01 71 23 69 73", note: "8码" },
  { channel: "爆发Top5", picks: "06 23 54 61 71", note: "方案2精选" },
  { channel: "防守Top3", picks: "03 25 15", note: "建议回避" },
  { channel: "跨规则共识", picks: "06 11 23 61", note: "多规则同时推荐" },
  { channel: "钻石共振", picks: "12 46", note: "≥4模块 · 仅参考" },
  { channel: "金级共振", picks: "06 11 23 33", note: "3模块 · 仅参考" },
];

const REVIEW_ROWS = [
  { module: "HE5", hit: "3/5", lift: "2.40x", detail: "32 46 70" },
  { module: "Trinity5", hit: "0/5", lift: "0.00x", detail: "全空" },
  { module: "Trinity12", hit: "3/12", lift: "1.00x", detail: "27 36 75" },
  { module: "AI5", hit: "2/5", lift: "1.60x", detail: "32 46" },
  { module: "AI12", hit: "4/12", lift: "1.33x", detail: "18 27 32 46" },
  { module: "mRMR12", hit: "5/12", lift: "1.67x", detail: "10 12 27 69 75" },
  { module: "纯净池高置信", hit: "0/3", lift: "0.00x", detail: "全空" },
  { module: "纯净池全量", hit: "3/12", lift: "1.00x", detail: "10 12 69" },
  { module: "爆发Top5", hit: "1/5", lift: "0.80x", detail: "70" },
  { module: "防守Top3", hit: "3/3", lift: "—", detail: "回避 37 55 71" },
];

export default function Kl8DailyAnalysis20260722() {
  return (
    <Stack gap={20} style={{ padding: 24, maxWidth: 1120 }}>
      <Stack gap={6}>
        <H1>快乐8 每日分析控制面板</H1>
        <Text tone="secondary">
          2026-07-22 · 目标期 2026193 · 开奖复盘 2026192 · Source:
          reports/daily_analysis_report_20260722.md
        </Text>
        <Row gap={8} style={{ flexWrap: "wrap" }}>
          <Pill tone="success" size="sm">
            数据校验全通过
          </Pill>
          <Pill tone="warning" size="sm">
            自学习冻结 WF=1.00
          </Pill>
          <Pill tone="warning" size="sm">
            信标 Level1 ×0.5
          </Pill>
          <Pill tone="neutral" size="sm">
            环境 平衡震荡期
          </Pill>
          <Pill tone="neutral" size="sm">
            EF0.50 RW0.20 FO0.30
          </Pill>
          <Pill tone="info" size="sm">
            KL Z=0.62σ
          </Pill>
        </Row>
      </Stack>

      <Grid columns={4} gap={12}>
        <Stat value="1.20x" label="近10期 HE5 Lift" tone="success" />
        <Stat value="0.96x" label="近10期 AI5 Lift" />
        <Stat value="REFERENCE" label="内部提纯状态" tone="warning" />
        <Stat value="无需调整" label="深度优化决策" tone="success" />
      </Grid>

      <Callout tone="success" title="上期亮点与优化结论">
        2026192 期 HE5 命中 3/5（Lift=2.40x），mRMR 5/12（1.67x），防守Top3
        全成功。近10期主通道仍贴近随机基线（HE5 1.20x / Tr12 0.97x / AI5
        0.96x），无显著深度优化空间。自学习保持冻结；极速爆破/极高阶已移除。本期决策：无需调整。
      </Callout>

      <Grid columns={2} gap={16}>
        <Card>
          <CardHeader>近10期命中数趋势 (Top5通道)</CardHeader>
          <CardBody>
            <LineChart
              categories={HIT_TREND.map((d) => d.period)}
              series={[
                { name: "HE5", data: HIT_TREND.map((d) => d.HE5) },
                { name: "Tr5", data: HIT_TREND.map((d) => d.Tr5) },
                { name: "AI5", data: HIT_TREND.map((d) => d.AI5) },
              ]}
              height={220}
            />
            <Text tone="secondary" size="sm">
              Source: 近10期日报对账 · 期号后缀 183–192 · 单位：命中个数/5
            </Text>
          </CardBody>
        </Card>
        <Card>
          <CardHeader>近10期模块 Lift vs 随机基线(=1.0)</CardHeader>
          <CardBody>
            <BarChart
              categories={MODULE_LIFT.map((d) => d.label)}
              series={[{ name: "Lift", data: MODULE_LIFT.map((d) => d.lift) }]}
              height={220}
            />
            <Text tone="secondary" size="sm">
              Source: reports 对账 · 基线 Top5=1.25 / Top12=3.00
            </Text>
          </CardBody>
        </Card>
      </Grid>

      <Card>
        <CardHeader trailing={<Pill tone="info" size="sm">2026192</Pill>}>
          上期复盘明细
        </CardHeader>
        <CardBody>
          <Table
            headers={["模块", "命中", "Lift", "命中号码"]}
            rows={REVIEW_ROWS.map((r) => [r.module, r.hit, r.lift, r.detail])}
          />
        </CardBody>
      </Card>

      <Card>
        <CardHeader trailing={<Pill tone="success" size="sm">2026193</Pill>}>
          今日各通道推荐
        </CardHeader>
        <CardBody>
          <Table
            headers={["通道", "号码", "说明"]}
            rows={RECS.map((r) => [r.channel, r.picks, r.note])}
          />
        </CardBody>
      </Card>

      <Divider />
      <Text tone="secondary" size="sm">
        落盘：reports/daily_analysis_report_20260722.md ·
        reports/控制面板_20260722.txt · reports/可复制推荐_2026193.txt ·
        提纯仅参考不驱动权重
      </Text>
      <Spacer />
    </Stack>
  );
}

# -*- coding: utf-8 -*-
import os

html_snippet = '''
      <!-- ═══════════ TAB: 定金选2决策驾驶舱 ═══════════ -->
      <div v-show="activeTab === 'gold_pick2_cockpit'" class="space-y-6">
        <!-- 头部概览条 -->
        <div class="glass-panel p-5">
          <div class="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
            <div>
              <div class="flex items-center gap-2">
                <span class="text-xl">💎</span>
                <h2 class="text-lg font-bold text-cyan-300">定金选2决策驾驶舱 (Gold Pick 2 Trading Cockpit)</h2>
                <span class="text-xs px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 font-mono border border-amber-500/30">
                  双重金胆法 · 7维特征加权 · 条件共现配对
                </span>
              </div>
              <p class="text-xs text-slate-400 mt-1">
                7维透明特征评分（图论耦合、马尔可夫、遗漏回归、Bollinger、趋势惩罚、信号平衡），温号池精选核心金胆与热号金胆双核配对。
              </p>
            </div>
            <div class="flex items-center gap-3">
              <button @click="triggerGoldPick2Run" :disabled="isRunning" class="cyber-btn cyber-btn-gold text-xs">
                <span>⚡</span>
                <span>{{ isRunning ? '推演中...' : '一键选2推演' }}</span>
              </button>
              <button @click="fetchGoldPick2Summary" class="cyber-btn cyber-btn-cyan text-xs">
                🔄 刷新数据
              </button>
            </div>
          </div>

          <!-- 核心指标摘要卡片 -->
          <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mt-5" v-if="goldPick2Summary">
            <div class="p-3 rounded-lg bg-slate-900/90 border border-slate-800">
              <div class="text-[11px] text-slate-400">目标研判期号</div>
              <div class="text-xl font-bold font-mono text-amber-300 mt-0.5">第 {{ goldPick2Summary.target_period }} 期</div>
              <div class="text-[10px] text-slate-500 font-mono mt-0.5">基于第 {{ goldPick2Summary.latest_period }} 期历史</div>
            </div>

            <div class="p-3 rounded-lg bg-slate-900/90 border border-slate-800">
              <div class="text-[11px] text-slate-400">核心金胆 (加权Z最高)</div>
              <div class="flex items-center gap-2 mt-0.5">
                <span class="text-2xl font-bold font-mono text-amber-400">
                  {{ String(goldPick2Summary.golden).padStart(2, '0') }}
                </span>
                <span class="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 font-mono">
                  遗漏 {{ goldPick2Summary.gap ? goldPick2Summary.gap[goldPick2Summary.golden] : 0 }} 期
                </span>
              </div>
              <div class="text-[10px] text-slate-500 font-mono mt-0.5">温号池优选单码</div>
            </div>

            <div class="p-3 rounded-lg bg-slate-900/90 border border-slate-800">
              <div class="text-[11px] text-slate-400">热号金胆 (近20期最热)</div>
              <div class="flex items-center gap-2 mt-0.5">
                <span class="text-2xl font-bold font-mono text-cyan-400">
                  {{ String(goldPick2Summary.hot).padStart(2, '0') }}
                </span>
                <span class="text-[10px] px-1.5 py-0.5 rounded bg-cyan-500/20 text-cyan-300 font-mono">
                  遗漏 {{ goldPick2Summary.gap ? goldPick2Summary.gap[goldPick2Summary.hot] : 0 }} 期
                </span>
              </div>
              <div class="text-[10px] text-slate-500 font-mono mt-0.5">旁证对齐参考</div>
            </div>

            <div class="p-3 rounded-lg bg-slate-900/90 border border-slate-800">
              <div class="text-[11px] text-slate-400">样本外置信评级</div>
              <div class="text-base font-bold font-mono text-emerald-300 mt-1 truncate" v-if="goldPick2Summary.confidence">
                {{ goldPick2Summary.confidence.badge }} {{ goldPick2Summary.confidence.title }}
              </div>
              <div class="text-[10px] text-slate-400 font-mono mt-0.5" v-if="goldPick2Summary.confidence">
                Lift: {{ goldPick2Summary.confidence.lift }}x | z={{ goldPick2Summary.confidence.z_score }}
              </div>
            </div>
          </div>
        </div>

        <!-- 双核 4 象限卡片展示区 -->
        <div class="grid grid-cols-1 lg:grid-cols-12 gap-6" v-if="goldPick2Summary">
          <!-- 左侧 6 列：Top 5 黄金配对组合 (以金胆为核) -->
          <div class="lg:col-span-6 glass-panel p-5 space-y-4 border border-amber-500/40 bg-gradient-to-b from-amber-950/20 to-slate-950/80">
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <span class="text-lg">💎</span>
                <h3 class="text-base font-bold text-amber-300">Top 5 黄金配对组合 (以金胆为核)</h3>
              </div>
              <span class="text-xs px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 font-mono">
                金胆: {{ String(goldPick2Summary.golden).padStart(2, '0') }}
              </span>
            </div>
            <p class="text-xs text-slate-400">
              以加权Z核心金胆为锚点，依据条件共现强度与双核金胆分综合优选的 Top 5 选2组合。
            </p>

            <div class="space-y-3 pt-1">
              <div v-for="(p, idx) in (goldPick2Summary.top5_golden || [])" :key="p.pair_str"
                   class="p-3.5 rounded-xl bg-slate-900/90 border border-slate-800 flex items-center justify-between hover:border-amber-500/50 transition">
                <div class="flex items-center gap-3">
                  <span class="text-xs font-mono font-bold px-2 py-1 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30">
                    Top {{ idx + 1 }}
                  </span>
                  <div class="flex items-center gap-2">
                    <span class="lottery-ball ball-gold text-sm font-bold">{{ String(p.pair[0]).padStart(2, '0') }}</span>
                    <span class="text-slate-500 font-bold">-</span>
                    <span class="lottery-ball ball-cyan text-sm font-bold">{{ String(p.pair[1]).padStart(2, '0') }}</span>
                  </div>
                  <span v-if="p.is_hot_overlap" class="text-[10px] px-1.5 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/30 font-bold">
                    ★ 与热胆重叠
                  </span>
                </div>
                <div class="text-right">
                  <div class="text-xs font-mono font-bold text-cyan-300">评分: {{ p.weight }}</div>
                  <div class="text-[10px] text-slate-500 font-mono">共现 {{ p.co_count }} 次</div>
                </div>
              </div>
            </div>
          </div>

          <!-- 右侧 6 列：热号金胆配对 + 温号池与交叉风控 -->
          <div class="lg:col-span-6 space-y-6">
            <!-- 热号金胆配对 -->
            <div class="glass-panel p-5 space-y-4 border border-cyan-500/40">
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-2">
                  <span class="text-lg">🥇</span>
                  <h3 class="text-base font-bold text-cyan-300">热号金胆配对组合 (旁证辅助)</h3>
                </div>
                <span class="text-xs px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-300 font-mono">
                  热胆: {{ String(goldPick2Summary.hot).padStart(2, '0') }}
                </span>
              </div>
              <div class="grid grid-cols-2 md:grid-cols-3 gap-2.5">
                <div v-for="(p, idx) in (goldPick2Summary.top5_hot || [])" :key="p.pair_str"
                     class="p-2.5 rounded-lg bg-slate-900/80 border border-slate-800 flex items-center justify-between">
                  <div class="flex items-center gap-1.5">
                    <span class="text-[10px] font-mono text-slate-500">T{{ idx + 1 }}</span>
                    <span class="font-mono font-bold text-xs text-white">[{{ p.pair_str }}]</span>
                  </div>
                  <span class="text-[10px] font-mono text-cyan-400">{{ p.weight }}</span>
                </div>
              </div>
            </div>

            <!-- 温号池 (遗漏4-8期) 态势矩阵 -->
            <div class="glass-panel p-5 space-y-3">
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-2">
                  <span class="text-lg">♨️</span>
                  <h3 class="text-sm font-bold text-slate-100">温号池态势矩阵 (遗漏 4-8 期)</h3>
                </div>
                <span class="text-xs font-mono text-amber-400">
                  共 {{ (goldPick2Summary.warm_pool || []).length }} 码候选
                </span>
              </div>
              <div class="flex flex-wrap gap-2 py-1 max-h-[120px] overflow-y-auto pr-1">
                <span v-for="n in (goldPick2Summary.warm_pool || [])" :key="n"
                      class="lottery-ball text-xs font-bold cursor-pointer hover:scale-110 transition"
                      :class="n === goldPick2Summary.golden ? 'ball-gold shadow-[0_0_10px_rgba(245,158,11,0.5)] font-black' : (n === goldPick2Summary.hot ? 'ball-cyan' : 'bg-slate-900 border border-slate-700 text-slate-300')"
                      @click="openBallDetail({number: n})">
                  {{ String(n).padStart(2, '0') }}
                </span>
              </div>
              <p class="text-[11px] text-slate-400 leading-relaxed">
                💡 统计学证明：快乐8 遗漏 4-8 期的温号处于绝佳回补窗口期，具备较高的反弹兑现期望。
              </p>
            </div>

            <!-- 主系统多维交叉风控 -->
            <div class="glass-panel p-4 space-y-2 border border-slate-800" v-if="goldPick2Summary.cross_validation">
              <div class="flex items-center justify-between">
                <span class="text-xs font-bold text-slate-300 flex items-center gap-1.5">
                  <span>🛡️</span> 主系统多维模型交叉风控
                </span>
                <span class="text-xs font-bold font-mono"
                      :class="goldPick2Summary.cross_validation.golden_killed_by_killseeker ? 'text-rose-400' : 'text-emerald-400'">
                  {{ goldPick2Summary.cross_validation.safety_audit }}
                </span>
              </div>
              <div class="flex flex-wrap gap-2 pt-1 text-[11px] font-mono">
                <span class="px-2 py-0.5 rounded"
                      :class="goldPick2Summary.cross_validation.golden_in_trinity12 ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30' : 'bg-slate-900 text-slate-500'">
                  {{ goldPick2Summary.cross_validation.golden_in_trinity12 ? '✓ Trinity12共振' : '— 无Trinity共振' }}
                </span>
                <span class="px-2 py-0.5 rounded"
                      :class="goldPick2Summary.cross_validation.golden_in_he5 ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30' : 'bg-slate-900 text-slate-500'">
                  {{ goldPick2Summary.cross_validation.golden_in_he5 ? '★ Hidden Energy 5' : '— 无HE5覆盖' }}
                </span>
                <span class="px-2 py-0.5 rounded"
                      :class="goldPick2Summary.cross_validation.golden_in_spatial_points ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30' : 'bg-slate-900 text-slate-500'">
                  {{ goldPick2Summary.cross_validation.golden_in_spatial_points ? '✓ 空间重点点位' : '— 重点点位未覆盖' }}
                </span>
                <span class="px-2 py-0.5 rounded"
                      :class="goldPick2Summary.cross_validation.golden_in_suppression ? 'bg-purple-500/20 text-purple-300 border border-purple-500/30' : 'bg-slate-900 text-slate-500'">
                  {{ goldPick2Summary.cross_validation.golden_in_suppression ? '✓ 影子反弹共振' : '— 无反弹信号' }}
                </span>
                <span class="px-2 py-0.5 rounded"
                      :class="goldPick2Summary.cross_validation.golden_killed_by_killseeker ? 'bg-rose-500/30 text-rose-300 border border-rose-500/50 font-bold' : 'bg-emerald-500/10 text-emerald-400'">
                  {{ goldPick2Summary.cross_validation.golden_killed_by_killseeker ? '⚠️ 命中KillSeeker杀号' : '✓ 杀号安全校验通过' }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- ═══════════ TAB: 选2样本外滚动复盘 ═══════════ -->
      <div v-show="activeTab === 'gold_pick2_review'" class="space-y-6">
        <!-- 头部对账指标 -->
        <div class="glass-panel p-5">
          <div class="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
            <div>
              <div class="flex items-center gap-2">
                <span class="text-xl">📊</span>
                <h2 class="text-lg font-bold text-cyan-300">定金选2 Walk-Forward 滚动样本外对账流水</h2>
              </div>
              <p class="text-xs text-slate-400 mt-1">
                无任何未来函数泄露：每期严格仅使用该期之前的数据逐期推演，对账金胆命中率、热胆命中率与 Top1 组合中2/中1。
              </p>
            </div>
            <div class="flex items-center gap-2">
              <span class="text-xs text-slate-400">选择复盘期数:</span>
              <div class="flex items-center gap-1">
                <button v-for="n in [10, 20, 30, 50]" :key="n"
                        @click="fetchGoldPick2Review(n)"
                        class="px-2.5 py-1 rounded text-xs font-mono transition border"
                        :class="goldPick2ReviewPeriods === n ? 'bg-cyan-500/30 text-cyan-300 border-cyan-500/60 font-bold' : 'bg-slate-900 text-slate-400 border-slate-800 hover:border-slate-700'">
                  {{ n }}期
                </button>
              </div>
            </div>
          </div>

          <!-- 指标卡 -->
          <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mt-5" v-if="goldPick2Review && goldPick2Review.stats">
            <div class="p-4 rounded-xl bg-slate-900/90 border border-slate-800 space-y-1">
              <div class="text-xs text-slate-400">核心金胆命中率</div>
              <div class="flex items-baseline gap-2">
                <span class="text-2xl font-bold font-mono text-amber-400">{{ goldPick2Review.stats.golden_hit_rate }}%</span>
                <span class="text-xs font-mono font-bold" :class="goldPick2Review.stats.golden_lift >= 1.0 ? 'text-emerald-400' : 'text-slate-400'">
                  (Lift {{ goldPick2Review.stats.golden_lift }}x)
                </span>
              </div>
              <div class="text-[10px] text-slate-500 font-mono">
                命中 {{ goldPick2Review.stats.golden_hit_count }} / {{ goldPick2Review.stats.n_periods }} 期 (基线 25.0%)
              </div>
            </div>

            <div class="p-4 rounded-xl bg-slate-900/90 border border-slate-800 space-y-1">
              <div class="text-xs text-slate-400">热号金胆命中率</div>
              <div class="flex items-baseline gap-2">
                <span class="text-2xl font-bold font-mono text-cyan-300">{{ goldPick2Review.stats.hot_hit_rate }}%</span>
                <span class="text-xs font-mono font-bold text-cyan-400">(Lift {{ goldPick2Review.stats.hot_lift }}x)</span>
              </div>
              <div class="text-[10px] text-slate-500 font-mono">
                命中 {{ goldPick2Review.stats.hot_hit_count }} / {{ goldPick2Review.stats.n_periods }} 期 (基线 25.0%)
              </div>
            </div>

            <div class="p-4 rounded-xl bg-slate-900/90 border border-slate-800 space-y-1">
              <div class="text-xs text-slate-400">Top 1 组合中2率 (全中)</div>
              <div class="flex items-baseline gap-2">
                <span class="text-2xl font-bold font-mono text-emerald-400">{{ goldPick2Review.stats.top1_both_rate }}%</span>
                <span class="text-xs font-mono font-bold text-emerald-400">(Lift {{ goldPick2Review.stats.top1_both_lift }}x)</span>
              </div>
              <div class="text-[10px] text-slate-500 font-mono">
                中2 {{ goldPick2Review.stats.top1_both_count }} 期 (基线 6.01%) · 至少中1: {{ goldPick2Review.stats.top1_one_rate }}%
              </div>
            </div>

            <div class="p-4 rounded-xl bg-slate-900/90 border border-slate-800 space-y-1">
              <div class="text-xs text-slate-400">温号池单码命中率</div>
              <div class="flex items-baseline gap-2">
                <span class="text-2xl font-bold font-mono text-purple-300">{{ goldPick2Review.stats.warm_pool_hit_rate }}%</span>
              </div>
              <div class="text-[10px] text-slate-500 font-mono">遗漏 4-8 期温态回补平均命中</div>
            </div>
          </div>
        </div>

        <!-- 历史流水表格 -->
        <div class="glass-panel p-5 space-y-4">
          <div class="flex items-center justify-between">
            <h3 class="text-sm font-bold text-slate-100 flex items-center gap-2">
              <span>📋</span> 近期逐期对账明细列表
            </h3>
            <span class="text-xs text-slate-400 font-mono" v-if="goldPick2Review && goldPick2Review.stats">
              共 {{ goldPick2Review.stats.n_periods }} 期样本外流水
            </span>
          </div>

          <div class="overflow-x-auto">
            <table class="cyber-table w-full text-left">
              <thead>
                <tr>
                  <th>期号</th>
                  <th>核心金胆</th>
                  <th>热号金胆</th>
                  <th>金胆对账</th>
                  <th>热胆对账</th>
                  <th>Top 1 组合</th>
                  <th>组合中奖</th>
                  <th>温号池命中</th>
                  <th>开奖真实球</th>
                </tr>
              </thead>
              <tbody v-if="goldPick2Review && goldPick2Review.rows">
                <tr v-for="row in goldPick2Review.rows" :key="row.period">
                  <td class="font-mono font-bold text-cyan-400">{{ row.period }}</td>
                  <td class="font-mono font-bold text-amber-300">
                    <span class="lottery-ball ball-gold !w-6 !h-6 !text-xs inline-flex items-center justify-center mr-1">
                      {{ String(row.golden).padStart(2, '0') }}
                    </span>
                  </td>
                  <td class="font-mono text-cyan-300">
                    <span class="lottery-ball ball-cyan !w-6 !h-6 !text-xs inline-flex items-center justify-center mr-1">
                      {{ String(row.hot).padStart(2, '0') }}
                    </span>
                  </td>
                  <td>
                    <span class="px-2 py-0.5 rounded font-mono font-bold text-xs"
                          :class="row.golden_hit ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30' : 'bg-slate-800 text-slate-500'">
                      {{ row.golden_hit ? '✅ 命中' : '❌ 未中' }}
                    </span>
                  </td>
                  <td>
                    <span class="px-2 py-0.5 rounded font-mono text-xs"
                          :class="row.hot_hit ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30' : 'bg-slate-800 text-slate-500'">
                      {{ row.hot_hit ? '✅ 命中' : '❌ 未中' }}
                    </span>
                  </td>
                  <td class="font-mono text-xs text-white">
                    [{{ row.top1_str }}]
                  </td>
                  <td>
                    <span class="px-2 py-0.5 rounded font-mono font-bold text-xs"
                          :class="row.top1_both ? 'bg-amber-500 text-slate-950 shadow-[0_0_8px_rgba(245,158,11,0.5)]' : (row.top1_one ? 'bg-cyan-500/20 text-cyan-300' : 'bg-slate-800 text-slate-500')">
                      {{ row.top1_both ? '🎉 中 2' : (row.top1_one ? '· 中 1' : '—') }}
                    </span>
                  </td>
                  <td class="font-mono text-xs text-purple-300">
                    {{ row.warm_hits }}/{{ row.warm_total }}
                  </td>
                  <td class="font-mono text-[11px] text-slate-400">
                    <span v-for="n in row.actual_nums" :key="n"
                          class="inline-block mr-1"
                          :class="n === row.golden ? 'text-amber-300 font-bold underline' : (n === row.hot ? 'text-cyan-300 font-bold' : 'text-slate-500')">
                      {{ String(n).padStart(2, '0') }}
                    </span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- ═══════════ TAB: 定金选2研报中心 ═══════════ -->
      <div v-show="activeTab === 'gold_pick2_logs'" class="space-y-6">
        <div class="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <!-- 左侧：历史预测列表 -->
          <div class="lg:col-span-4 space-y-4">
            <div class="glass-panel p-4 space-y-3">
              <div class="flex items-center justify-between">
                <h3 class="text-sm font-bold text-slate-100 flex items-center gap-2">
                  <span>📑</span> 定金选2历史研报清单
                </h3>
                <button @click="fetchGoldPick2Logs" class="text-xs text-cyan-400 hover:underline">刷新</button>
              </div>

              <div class="space-y-2 max-h-[650px] overflow-y-auto pr-1">
                <div v-for="item in goldPick2Logs" :key="item.filename"
                     class="p-3 rounded-lg border cursor-pointer transition flex flex-col gap-1"
                     :class="selectedGoldPick2Log && selectedGoldPick2Log.filename === item.filename ? 'bg-amber-500/20 border-amber-400 shadow-[0_0_10px_rgba(245,158,11,0.3)]' : 'bg-slate-900/60 border-slate-800 hover:border-slate-700'"
                     @click="selectGoldPick2Log(item)">
                  <div class="flex items-center justify-between">
                    <span class="text-xs font-bold text-slate-200">{{ item.title }}</span>
                    <span class="text-[10px] px-1.5 py-0.2 rounded font-mono bg-amber-500/20 text-amber-300">
                      第 {{ item.period }} 期
                    </span>
                  </div>
                  <div class="text-[10px] text-slate-500 font-mono">{{ item.mtime }}</div>
                </div>
              </div>
            </div>
          </div>

          <!-- 右侧：研报纯文本渲染器 -->
          <div class="lg:col-span-8 space-y-4">
            <div class="glass-panel p-6 min-h-[650px]">
              <div class="flex items-center justify-between pb-4 mb-4 border-b border-slate-800">
                <div class="flex items-center gap-2">
                  <span class="text-lg">📜</span>
                  <h3 class="text-base font-bold text-amber-300">
                    {{ selectedGoldPick2Log ? selectedGoldPick2Log.title : '请选择左侧研报查看' }}
                  </h3>
                </div>
                <span class="text-xs text-slate-400 font-mono" v-if="selectedGoldPick2Log">{{ selectedGoldPick2Log.mtime }}</span>
              </div>

              <pre class="bg-slate-950/80 p-4 rounded-xl border border-slate-800 text-slate-200 text-xs font-mono leading-relaxed overflow-y-auto max-h-[580px] whitespace-pre-wrap">{{ goldPick2LogDetail || '正在加载预测研报内容...' }}</pre>
            </div>
          </div>
        </div>
      </div>
'''

target_tag = '<!-- ═══════════ TAB: Gemini 选2预测决策大屏 ═══════════ -->'

with open('frontend/static/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

if target_tag in content:
    new_content = content.replace(target_tag, html_snippet + '\n      ' + target_tag)
    with open('frontend/static/index.html', 'w', encoding='utf-8') as f:
        f.write(new_content)
    with open('web_app/static/index.html', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print('Inserted gold_pick2 tabs into both frontend and web_app index.html successfully.')
else:
    print('Target tag not found!')

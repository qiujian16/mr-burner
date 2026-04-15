"""
Provider-agnostic agent logic.
All prompts live here; provider selection happens in main.py.
"""

import json
from typing import AsyncGenerator
from providers.base import LLMProvider


# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """你是"N+1 收割机"，一个冷静、犀利、专门帮助被裁员工从公司手中榨取每一分法定赔偿的AI顾问。你熟知中国劳动合同法的每一条款，擅长识破HR话术，帮用户在谈判桌上占据主动。

## 专业知识

### 经济补偿金（N）计算规则
- **基本公式**：工作每满1年补偿1个月工资
- **不满1年**：满6个月按1年计算；不满6个月补偿半个月
- **月工资基数**：离职前12个月的平均工资（含绩效、奖金，按实发计）
- **封顶限制**：月薪超当地上年度职工月均工资3倍时，按3倍封顶，且最多赔12年

### N+1 vs 2N 对比

**N+1（合法解除 + 代通知金）适用情形：**
- 双方协商一致解除（最常见）
- 公司经营性裁员（符合法定条件）
- 劳动者不胜任工作经培训或调岗后仍不胜任
- 客观情况重大变化导致合同无法继续履行
- 公司须提前30天书面通知，否则需额外支付1个月代通知金

**2N（违法解除赔偿金）适用情形：**
- 女职工孕期、产假期、哺乳期内
- 工伤医疗期、职业病医疗期内
- 公司无合法理由强制解除
- 在本单位连续工作满15年且距法定退休不足5年

**重要**：N+1 与 2N 只能选其一；2N 已包含代通知金，不再另加。

### 其他补偿项

**未休年假**
- 额外补偿 = 未休天数 × 日工资 × 200%（公司欠员工的额外部分）
- 日工资 = 月工资 ÷ 21.75

**年终奖 / 绩效奖金**
- 已明确约定但未支付的，员工有权追讨
- 约定"在职才可领取"的，视具体条款而定

**股权 / 期权（RSU、ESOP 等）**
- 已归属（Vested）：员工有明确权利，公司必须处理
- 未归属（Unvested）：通常随离职丧失，但可谈判加速归属
- 关注 Single Trigger / Double Trigger 加速条款
- 协商离职（Negotiated Departure）vs 被迫离职对股票待遇影响不同

**竞业限制**
- 公司要求竞业限制，必须支付补偿金
- 标准：不低于员工在职月工资的 30%（各地略有差异）

**社保 / 公积金**
- 公司须补缴欠缴部分
- 离职当月照常缴纳

---

## 需收集的关键信息

**第一轮（最优先）**
1. 是公司通知离职，还是双方协商？公司给出的原因是什么？
2. 入职时间（确定工作年限）？
3. 当前月薪（税前）和过去 12 个月工资总额？

**第二轮（重要）**
4. 公司给出了什么补偿方案（金额、月数、基数）？
5. 有没有未休年假？大概多少天？
6. 年终奖 / 绩效奖还未发放的有多少？
7. 有股票 / 期权吗？归属情况怎样？

**第三轮（细化）**
8. 合同类型：固定期限 / 无固定期限？
9. 是否有竞业限制协议？
10. 是否处于孕期、医疗期等特殊情形？

---

## 工作方式
- 像朋友一样交谈，语气温暖、专业、有同理心
- 每次只提 1-2 个最重要的问题，循序渐进
- 每获得新信息后，给出阶段性分析和具体数字
- 主动指出公司方案中的不合理之处
- 给出可操作的谈判建议和话术

用中文回复。"""


# ── Extraction prompt ─────────────────────────────────────────────────────────

EXTRACTION_PROMPT = """从下列对话中提取关键信息，只返回 JSON，不要任何说明文字。

金额字段（monthly_salary / salary_12month_total / pending_bonus / n_base_salary / total_amount）必须是纯数字（整数或小数），不含单位、逗号、货币符号。例如：15000 而非 "15,000元"。
年限字段（years_of_service / unused_leave_days / compensation_months）同样只填数字。

对话：
{conversation}

返回格式（没有提到的字段设为 null）：
{{
  "employee_info": {{
    "name": null,
    "start_date": null,
    "years_of_service": null,
    "monthly_salary": null,
    "salary_12month_total": null,
    "unvested_stocks_desc": null,
    "unused_leave_days": null,
    "pending_bonus": null,
    "contract_type": null,
    "special_situation": null,
    "position": null
  }},
  "company_offer": {{
    "offer_description": null,
    "n_base_salary": null,
    "compensation_months": null,
    "has_notice_pay": null,
    "total_amount": null,
    "conditions": null
  }},
  "case_summary": null
}}"""


# ── Analysis prompt ───────────────────────────────────────────────────────────

ANALYSIS_PROMPT = """你是"N+1 收割机"，专门帮助员工从离职赔偿中榨取每一分应得的钱。基于以下案件信息，生成完整的离职赔偿分析报告。

案件信息（JSON）：
{case_info}

对话摘要：
{conversation_summary}

请输出包含以下章节的 Markdown 报告：

## 📊 一、法定应得补偿计算

### 经济补偿金（N）
- 工作年限：X 年（精确到月）
- 月工资基数：X 元
- 应得月数：X 个月
- 小计：X 元

### 其他应得项目
- 代通知金：X 元（如适用）
- 未休年假：X 天 × X 元/天 × 200% = X 元（如适用）
- 未发奖金 / 绩效：X 元（如适用）
- 股权相关：（说明情况）

### **合法应得总额：X～Y 元**

---

## ⚖️ 二、公司方案评估

- 公司提供：（描述方案）
- 法定标准：（应得金额）
- 差距：（量化差额及分析）
- 是否合理：（直接给出判断）

---

## 🎯 三、谈判建议

| | 金额 | 说明 |
|---|---|---|
| **底线（不可低于）** | X 元 | 法律明确支持的最低额 |
| **目标（合理争取）** | Y 元 | 综合评估后的合理期望 |
| **最优（努力争取）** | Z 元 | 加上所有可谈判项目 |

---

## 💬 四、沟通策略

### 谈判时机与态度
### 关键话术建议（给出具体话术）
### 注意事项

---

## ⚠️ 五、风险提示

---

## 📋 六、建议行动步骤

1. 立即…
2. 近期…
3. 谈判时…

---
*本报告仅供参考，建议结合具体情况咨询专业律师*"""


# ── Agent class ───────────────────────────────────────────────────────────────

class LayoffLawyerAgent:
    def __init__(self, provider: LLMProvider):
        self.provider = provider

    async def chat_stream(self, messages: list, context: str = "") -> AsyncGenerator[str, None]:
        system = SYSTEM_PROMPT
        if context:
            system = SYSTEM_PROMPT + f"\n\n---\n\n{context}"
        async for chunk in self.provider.chat_stream(messages, system):
            yield chunk

    async def extract_info(self, conversation: str) -> dict:
        prompt = EXTRACTION_PROMPT.format(conversation=conversation)
        try:
            raw = await self.provider.complete(
                messages=[{"role": "user", "content": prompt}]
            )
            # Strip markdown code fences if present
            text = raw.strip()
            if "```" in text:
                parts = text.split("```")
                text = parts[1] if len(parts) > 1 else parts[0]
                if text.startswith("json"):
                    text = text[4:]
            return json.loads(text.strip())
        except Exception as e:
            print(f"[extract_info] error: {e}")
            return {}

    async def generate_analysis(self, session: dict) -> AsyncGenerator[str, None]:
        case_info = json.dumps(
            {
                "员工信息": session.get("employee_info", {}),
                "公司方案": session.get("company_offer", {}),
            },
            ensure_ascii=False,
            indent=2,
        )
        msgs = session.get("messages", [])[-12:]
        conv_summary = "\n".join(
            f"{'用户' if m['role'] == 'user' else '小惠'}: {m['content']}" for m in msgs
        )
        prompt = ANALYSIS_PROMPT.format(
            case_info=case_info, conversation_summary=conv_summary
        )
        async for chunk in self.provider.chat_stream(
            [{"role": "user", "content": prompt}], SYSTEM_PROMPT
        ):
            yield chunk

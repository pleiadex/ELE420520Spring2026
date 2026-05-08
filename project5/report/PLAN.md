# Project 5 Paper — Implementation Plan

## 최종 산출물 목록

| 파일 | 설명 |
|---|---|
| `report/paper.tex` | IEEE Transaction 2-column LaTeX 본문 |
| `report/references.bib` | 기존 bib 파일 (필요 항목 추가) |
| `report/figures/fig_system.tex` | TikZ 시스템 아키텍처 다이어그램 (input으로 포함) |
| `report/figures/fig_defense_flow.tex` | TikZ 방어 흐름도 (tier-1 → tier-2 결정 트리) |
| `report/figures/fig_mode_results.{png,pdf,svg}` | 모드별 accept rate + policy accuracy 막대 그래프 |
| `report/figures/fig_ablation.{png,pdf,svg}` | Tier ablation (boundary_tier2_only 프로파일) 결과 |

---

## 논문 구성 (≤3 pages, IEEE Transaction double-column)

### 분량 계획

```
Abstract              약 80 words          (~0.15 col)
I.   Introduction     약 180 words         (~0.5  col)
II.  System Design    약 200 words + 그림   (~0.8  col)  ← TikZ 두 개
III. Defense Impl.    약 200 words          (~0.6  col)
IV.  Results          약 250 words + 표+그림(~1.0  col)
V.   Conclusion       약 80 words           (~0.25 col)
References            별도 (페이지 카운트 X)
Appendix              run 절차 + code snippet
────────────────────────────────────────────
합계                  약 3 pages (본문)
```

---

## 스토리라인 (논리 흐름)

```
[Hook] 전력망 제어 명령은 구문(Syntax)이 맞으면 신뢰받는다
        ↓
[Problem] Type-C 공격: 구문은 정상, 내용만 물리적으로 위험
          → 프로토콜/IDS 레벨 탐지 불가 (Lin et al. 2016)
        ↓
[Approach] 실행 전 물리 결과를 relay 자체에서 예측해서 거부
           Tier-1: 하드 밴드  /  Tier-2: 선형 DC 심각도 점수
        ↓
[Key Result 1] 양쪽 tier 켜면 → 공격 100% 차단, latency < 0.3ms
[Key Result 2] boundary_tier2_only 프로파일에서 tier-2만이 결정권 가짐
               → tier-1으로는 구분 불가한 경계 케이스 처리 증명
[Key Result 3] FDIA(Type-A) 유무가 Type-C 방어 결과에 영향 없음
               → 읽기/쓰기 경로 방어가 독립적임 확인
        ↓
[Conclusion] DC 선형 모델 수준만으로도 실용적 방어 가능
             lightweight + fast + layered
```

---

## 섹션별 세부 내용

### Abstract
- Type-C 공격 정의 한 문장
- 방어 방법 (relay-side, two-tier) 한 문장
- 실험 규모 (164 runs, 328 events)
- 핵심 숫자: 100% attack blocking, < 0.3ms latency
- 결론 한 문장

### I. Introduction
- 스마트 그리드 제어 시스템 취약성 배경
- Type-A vs Type-C 구분 (Liu 2009, Lin 2016 cite)
- Type-C가 왜 기존 방어로 안 잡히는지
- 본 논문 기여 (contribution) bullet 3개:
  1. Mininet 기반 Type-C MitM 구현 및 시연
  2. Relay-side 2-tier 물리 사전 검증 방어 구현
  3. Tier 기여 분리를 위한 ablation study

### II. System Design & Threat Model
**A. Network Topology** (TikZ 그림 1)
- 3-switch Mininet 토폴로지
- cc → da → relay1~4 경로
- da가 MitM 위치임을 시각적으로 강조

**B. Attack Model**
- Type-A: da가 측정값 리턴 시 fdia_measure로 교체
- Type-C: da가 control 전달 시 setpoint를 8.0으로 교체
- 4개 실험 모드 표로 정리

**C. DNP3m Protocol**
- Poll (0x01) / Control (0x02) / Ack (0x0C) 간단 설명

### III. Defense Implementation
**A. Tier-1: Nominal Band Check**
- 수식: |sp - z_nom[k]| ≤ Δ_max
- Δ_max = 1.0 pu, 표로 nominal 값 일부 표시

**B. Tier-2: Linearized DC Consequence Score**
- WLS gain matrix 수식: G = (H^T W H)^{-1} H^T W
- severity = ||G Δz||_∞
- threshold = 0.10 pu
- boundary_tier2_only 프로파일 숫자 예시: sp=2.5 → severity≈0.112 > 0.10

**C. Decision Flow** (TikZ 그림 2 - 방어 흐름도)
- recv control → tier1? → (fail→reject) → tier2? → (fail→reject) → accept + update state

### IV. Experimental Results
**A. Setup**
- 4 modes × 2 tier1 × 2 tier2 × 3 profiles × 3 trials = 164 logs, 328 events

**B. Mode-level Outcomes** (그림: bar chart)
- Table: mode / accept rate / latency / policy accuracy
- baseline=fdia_only: 85.4% accept → FDIA가 Type-C 방어에 무관함
- typec_only=combined: 22.0% accept → 공격 명령 대부분 차단

**C. Confusion Analysis** (인라인 Table)
| benign fwd | benign blocked | attack fwd | attack blocked | accuracy |
|140|24|36|128|81.7%|
- 24 false block + 36 miss는 모두 tier 비활성화 ablation 셀에서 발생
- 완전 방어(tier1+tier2 on, typec mode) → 0 miss

**D. Tier Ablation** (그림: grouped bar)
- boundary_tier2_only 프로파일 중심
- tier2 on vs off: Δpolicy = ±1.0, Δfalse_block = ∓1.0
- tier1 on vs off on boundary_tier2_only: Δ = 0 (tier2가 처리하므로)
- Key message: tier-2가 유일하게 경계 케이스를 결정

### V. Conclusion
- 2-tier pre-execution check로 Type-C 완전 차단 + < 0.3ms
- ablation이 두 tier의 역할 분리 증명
- 한계: DC 선형 모델, 단일 aggregator, threshold 수동 튜닝
- Future: full AC model, cross-substation attestation

---

## 그림 계획

### 그림 1: 시스템 아키텍처 (TikZ, single-column)
```
[Control Center] ──→ [Data Aggregator] ──→ [Relay 1~4]
                      (MitM position)
                      Type-C: sp 교체
                      Type-A: measure 교체
```
- 노드를 박스로, 링크를 화살표로
- Type-C 공격 경로를 붉은색 점선으로 강조
- 방어 체크 위치(Relay 내부)를 녹색 박스로 표시

### 그림 2: 방어 결정 흐름 (TikZ, single-column)
```
Receive Control Command
        ↓
[Tier-1 Check: |sp - nom| ≤ 1.0?]
   NO → REJECT (tier1_band_violation)
   YES ↓
[Tier-2 Check: ||GΔz||∞ ≤ 0.10?]
   NO → REJECT (tier2_predicted_state_deviation)
   YES ↓
ACCEPT + Update State
```

### 그림 3: 모드별 결과 bar chart (Python, single-column, ~3.5in × 2.5in)
- x축: 4 modes
- y축 왼쪽: accept rate (bar)
- y축 오른쪽: median relay latency (line or secondary bar)
- IEEE style, font 8pt

### 그림 4: Ablation 결과 (Python, single-column, ~3.5in × 2.5in)
- x축: tier combination (T1on-T2on, T1on-T2off, T1off-T2on, T1off-T2off)
- y축: policy accuracy (grouped by profile: benign_nominal, boundary_safe_both, boundary_tier2_only)
- boundary_tier2_only에서 T2 off일 때 뚜렷한 차이 강조
- IEEE style, font 8pt

---

## Plot 생성 방법
- 가상환경: `~/workspace/venv`
- SciencePlots: `["science", "ieee"]` style
- 단일 컬럼 크기: figsize=(3.5, 2.5)
- 폰트: 8pt (tick, label 모두)
- 저장: PNG (300dpi), PDF, SVG

---

## 인용 키 (references.bib에서 사용할 것)
- `liuFalseDataInjection` → Liu et al. CCS 2009 (Type-A FDIA)
- `linSafetycriticalCyberphysicalAttacks2016` → Lin et al. HotSoS 2016 (Type-C + defense)
- `linChallengesOpportunitiesDetection2020` → Lin et al. Computer 2020 (survey)
- 추가 필요: Mininet cite (필요 시 web reference 추가)

---

## 실행 순서 (구현 시)

1. `report/figures/` 디렉토리 생성
2. Plot 생성 스크립트 작성 및 실행 (`~/workspace/venv` 사용)
3. TikZ 다이어그램 파일 작성 (fig_system.tex, fig_defense_flow.tex)
4. `paper.tex` 작성 (IEEE template, 본문 + \input 그림)
5. references.bib 확인/보완
6. 최종 확인: 3페이지 이내, 모든 cite 유효, 그림 caption 완성

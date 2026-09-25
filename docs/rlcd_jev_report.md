# RLCD Explained: What TypeSafe Has Actually Disclosed About Training Jev, What It Probably Means, and How to Use It Safely

*Research report, September 2026*

RLCD ("Reinforcement Learning for Calibrated Decisions") is a training objective, not a published algorithm. TypeSafe says it rewards Jev for "answers with epistemically honest probabilities" instead of for text people like (RLHF) or outputs a program can check (RLVR). As of September 24, 2026, though, the company has published no paper, reward function, dataset or calibration figure. Independent tests show Jev's raw probabilities rank answers well but are not reliably calibrated out of the box, especially on data unlike its training data. For safety-relevant work, treat Jev's numbers as scores you must recalibrate and re-validate on your own labeled data, per model version and per question wording.

## TL;DR

- **What RLCD is:** a vendor-named post-training objective. The reward is tied to whether stated probabilities match observed outcomes, and the training data is exclusively synthetic. TypeSafe has disclosed the goal and the data source only. The mechanism, reward function and dataset are unpublished, Almeida said "No, not yet" when asked about a paper, and no paper, preprint or technical report was found as of September 24, 2026.
- **How it most likely works (speculation):** probably something close to training the model's native output distribution with a proper scoring rule such as log loss or the Brier score. Under such rules, reporting your true belief is mathematically the best strategy. Published relatives are RLCR (Brier-augmented reward) and "Rewarding Doubt" (clipped log-score reward). None of this is confirmed by TypeSafe.
- **What the evidence says:** community audits of jev-1.13.0 found expected calibration error (ECE, the average gap between stated confidence and actual accuracy) ranging from about 0.03 on MMLU to 0.107–0.117 on out-of-distribution and sentiment data. The audits include Anthus (8,801 examples), scienthoon/jev-ood-calibration (900 tickets) and jujumilk3/jev-calibration-audit, catalogued in the GitHub list Yifan-Lan/awesome-jev-robustness. Choice answers run overconfident, and the "confidence" field is a formula computed from the top probability rather than a probability of being correct. Isotonic recalibration on a few hundred labeled examples fixed most of it in one study (ECE 0.117 → 0.008). For NAND failure-mode classification or ISO 26262 review, calibrate on your own data before setting any automation threshold.

## Key Findings

1. **The official disclosure is an objective plus a data claim, nothing more.** The launch post's comparison table says RLHF/RLVR optimize for "Human preference: writeups and chat responses that human raters prefer" and "Verifiable rewards: outputs that can be programmatically verified." RLCD optimizes for "Calibrated decisions: answers with epistemically honest probabilities on System One tasks." TechCrunch reports that Jev "is trained exclusively on synthetic data." No proper scoring rule is named anywhere in TypeSafe's own materials.
2. **Almeida frames RLCD as a "North Star" (a task), not an algorithm.** On Latent Space he said what he calls RLHF "is the task of instruction following. It's not about the PPO. That part doesn't matter," and "for us, RLCD is this new task." Read RLCD as "a new target for RL post-training," like the way DPO still counts as RLHF, not as a specific update rule you could reimplement.
3. **Research does show that preference-based post-training degrades calibration.** The GPT-4 technical report states the pre-trained model "is highly calibrated," but "after the post-training process, the calibration is reduced." Tian et al. (EMNLP 2023) replicated this on Llama-2-70B base vs. chat.
4. **Calibration is measurable and fixable after the fact, but only per distribution.** The Anthus study, 8,801 labeled examples on jev-1.13.0, reported raw ECE 0.117 for a Noul (yes/no) question. Platt scaling brought it to 0.052 and isotonic regression to 0.008. Across 11 question phrasings, raw ECE ranged from 0.064 to 0.160, and after isotonic recalibration from 0.006 to 0.018.
5. **"Probability" and "confidence" are different fields.** `probabilities` is the distribution over your options. `confidence` is a derived statistic of the distribution's shape; for Choice it has been reverse-engineered as (N·p_max − 1)/(N − 1). It is not the probability that the answer is correct, and Noul answers carry no confidence field at all.
6. **The name "RLCD" collides with an unrelated 2023 method:** Reinforcement Learning from Contrastive Distillation (Yang, Klein, Celikyilmaz, Peng and Tian, arXiv 2307.12950, ICLR 2024).

## Details

### 1. What TypeSafe has officially disclosed (vendor claims)

**Launch blog post ("Introducing System One Models & Jev," Diogo Almeida, Sep 15, 2026).** TypeSafe says it built "a new stack entirely focused on automation: with a new model architecture, parallel sampler for maximum efficiency, and training method we call Reinforcement Learning for Calibrated Decisions (RLCD)." The table's confidence row claims that LLMs, "even if prompted for a confidence estimate… tend to be overconfident and inconsistent," while Jev is "Calibrated: higher confidence means higher accuracy. More consistent: returns similar answers for similar inputs." The post's own evidence section covers speed, cost, type-safety and workflow evals. The workflow evals use "the average of GPT-6 Astra and Fable 5.1 as the reference answer." They measure agreement with other models, not calibration against ground truth.

The launch post has collapsed FAQ items: "Why was a new training algorithm needed?" and "Where does our training data come from?" Their text could not be rendered directly. Secondhand quotes (aiwiki.ai) say the answers argue that RLHF optimizes for "the text that a human rater prefers," which is "the wrong task for automation." They say RLVR "is great for tasks with simple programmatic verification, but most real-world judgement tasks don't fit into that shape," and that TypeSafe says "we make all the data ourselves." Treat these as unverified until you read the rendered page.

**Docs, AI primer (docs.typesafe.ai/introduction/machine-learning-primer).** The one-line definition: "Reinforcement learning for calibrated decisions trains TypeSafe to return decisions and calibrated probabilities instead of generated text." The primer also says "Higher probability should correspond to a greater chance that the answer is correct." It defines calibration at the group level: outcomes given 0.2 "should occur about 20% of the time… These rates describe groups of predictions, not a guarantee about any single answer." Its critique of RLHF: it "can also reward sycophancy and confident-sounding hallucinations," causes "mode dropping," and "Human preference and machine trustworthiness are different optimization targets."

**Confidence docs (docs.typesafe.ai/confidence).** "`confidence` is a statistic computed from the probability distribution the answer already gives you." Noul answers "don't carry one." The docs recommend three bands: act automatically at high confidence, proceed with caution in the middle, and at low confidence "Do not act." Their code example uses 0.5 as a floor and 0.9 for a destructive action. The key caveat is TypeSafe's own: "The correct threshold values depend on your domain and the performance of the model for your use case… test with your own data."

**TechCrunch interview (Tim Fernholz, Sep 18, 2026).** "Almeida says Jev is trained exclusively on synthetic data using a technique he calls 'reinforcement learning from calibrated decisions.'" Note the preposition: "from," where TypeSafe's docs say "for." He calls data "one of the best bets I've ever made in my life — better than our launch, in my opinion, better than RLHF," and says half the company "is a lab that basically owns this entire subfield of statistically well-understood synthetic data." TechCrunch also notes Almeida "is tight-lipped about the model's architecture, which outside observers suspect is built on top of an open-weight LLM."

**Latent Space podcast (Sep 21, 2026).** Asked whether TypeSafe had published a paper, Almeida said: "No, not yet." He confirmed all training data is synthetic and said TypeSafe does not want to train on user data because "real-world data has so much bias." He explained RLHF's calibration problem through mode dropping: mode-covering, calibrated distributions are "not overly punished about having outliers," whereas for long strings "calibration is, like, total poison." On model versions he said, "We will not change our models when we deploy them," but also that TypeSafe is "not promising long-term support for the models." That second point matters for configuration management.

**What is NOT published (confirmed as of Sep 24, 2026):** reward function or scoring rule, RL algorithm details, base model, parameter count, dataset composition or generation method, a paper or technical report, and any calibration metric (ECE, reliability diagram, Brier score) from TypeSafe. Systemonemodels.org reported that an arXiv search on September 20 returned zero results for the exact phrase.

### 2. RLCD vs. RLHF, RLAIF and RLVR

All four use reinforcement learning: the model produces an output, receives a scalar reward, and is nudged toward outputs that earn more reward. They differ in **what the reward measures.**

| | RLHF | RLAIF | RLVR | RLCD (as described) |
|---|---|---|---|---|
| Reward source | Reward model trained on human preference rankings; typically optimized with PPO (InstructGPT, Ouyang et al. 2022) | Same pipeline, but preference labels come from an AI judge guided by principles (e.g., Constitutional AI) | Automatic checker: answer key, unit tests, math verifier (DeepSeek-R1, Tulu 3) | Not published. Stated target: probabilities that match outcomes |
| Output | Free text | Free text | Free text, usually with reasoning traces | Typed answer + probability distribution (Choice, Score, Noul) |
| What it rewards | What sounds best to a rater | What sounds best to an AI judge | Being right (binary) | Being honestly uncertain: right at the stated rate |
| Effect on calibration | Degrades it (GPT-4 report; Tian et al. 2023) | Inherits preference-model biases | Binary rewards "do not penalize guessing," which can degrade calibration (RLCR paper) | Target property, but not independently confirmed; audits are mixed |
| Known failure modes | Sycophancy, overconfidence, mode dropping | Same, plus judge bias | Slower/costlier inference; jagged skills | TypeSafe's own jaggedness list: arithmetic, counting, dates, distracting state, adversarial content |
| Paper | Ouyang et al., arXiv 2203.02155 | Bai et al. 2022 | DeepSeek-R1, arXiv 2501.12948 | None |

**Why preference rewards push toward overconfidence (intuition).** Raters reading two answers tend to prefer the one that sounds sure and complete. A reward model trained on those rankings learns that assertive text scores higher, so the policy learns to assert. Nothing in the reward ever checks whether "I'm 95% sure" was right 95% of the time. The empirical signature is in the GPT-4 technical report's MMLU calibration plots (pre-trained vs. post-trained): the base model tracks the diagonal, and the post-trained model does not. Tian et al. found that for RLHF models, verbalized confidences are often better calibrated than the model's own token probabilities, often reducing ECE by a relative 50%. In other words, RLHF distorts the internal probabilities enough that asking the model in words works better. Calibration is also sensitive to how the request is phrased.

### 3. The likely technical underpinnings (informed speculation, clearly labeled)

TypeSafe has not named its reward. Prior research, though, makes the most plausible design fairly clear: a **proper scoring rule** used as the reward.

**Proper scoring rules.** A scoring rule grades a probability forecast against the outcome. It is *proper* if your expected score is best when you report your true belief. The two standard ones:
- **Brier score:** (q − y)², where q is the stated probability and y is 1 if the event happened, 0 otherwise. Lower is better.
- **Log loss:** −[y·ln q + (1−y)·ln(1−q)]. Lower is better, and it punishes confident errors extremely hard.

**Worked example: why a proper-scoring reward makes probabilities honest.** Say that for a certain kind of eMMC failure report, the model's evidence genuinely supports "wear-out" 70% of the time. Consider three reward schemes and what they teach the model to say:

- *Accuracy-only reward (RLVR-style):* +1 if the top answer is right. Expected reward is 0.7 whether the model says 0.51 or 0.99, so the number attached is never trained. Guessing confidently costs nothing.
- *Preference reward (RLHF-style):* if raters prefer confident-sounding answers, the reward rises with stated confidence, pushing q toward 1.0 regardless of the truth.
- *Brier penalty:* the expected penalty is 0.7·(1−q)² + 0.3·q².
  - Say q = 0.70: 0.7·0.09 + 0.3·0.49 = **0.210**
  - Say q = 0.50: 0.7·0.25 + 0.3·0.25 = 0.250
  - Say q = 1.00: 0.7·0 + 0.3·1 = 0.300
  - The minimum is exactly at the honest 0.70.
- *Log loss:* the expected penalty at q = 0.70 is 0.611, at q = 0.90 it is 0.765, and at q = 0.99 it is 1.389. Overclaiming is punished steeply.

So a policy maximizing a proper-scoring reward learns to report the frequency its evidence actually supports. That is what "epistemically honest probabilities" would mean mechanically.

**Published relatives.**
- **RLCR (Damani et al., "Beyond Binary Rewards," arXiv 2507.16806).** Trains reasoning models to output an answer plus a verbalized confidence. The reward augments a binary correctness score with a Brier score. It notes that binary rewards do not penalize guessing, which degrades calibration. It also warns that calibration-only rewards can be gamed: models may output deliberately incorrect answers with zero confidence to achieve perfect calibration rewards. That is why it keeps the correctness term.
- **Rewarding Doubt (Bani-Harouni, Stangel et al., arXiv 2503.02623, ICLR 2026).** Uses a reward based on the logarithmic scoring rule, clipped for numerical stability, and proves the optimal policy is perfectly calibrated.
- **Xu et al. (2024)** used the Brier score as an RL reward.

**How RLCD likely differs (speculation).** Those methods calibrate a number written inside generated text. Jev returns a native probability distribution over a fixed set of typed options, and the chosen answer is simply its argmax. That makes it closer to training a classic classifier with a multi-class proper scoring rule than to anything chat-shaped. Because the answer and its probability are one object, the RLCR-style hack of "answer wrong at zero confidence" is less available. Almeida's phrase "statistically well-understood synthetic data" hints, again speculatively, that TypeSafe may generate training items whose correct probabilities are known by construction, so the reward can target the true probability rather than a hard 0/1 label. One testable consequence: calibration should be best on data resembling the synthetic training distribution and should degrade under distribution shift. The independent audits below show exactly that pattern.

**Post-hoc tools you can apply yourself (established methods).**
- **ECE (expected calibration error):** bucket predictions by stated probability, compare each bucket's mean probability with its observed accuracy, and take the weighted average gap (Naeini, Cooper and Hauskrecht, AAAI 2015).
- **Temperature scaling / Platt scaling:** fit one or two parameters that sharpen or soften the probabilities. Cheap, but it can only fix smooth, sigmoid-shaped distortions.
- **Isotonic regression:** fits any monotone step function from raw to calibrated probability. It won on Jev because the distortion was not sigmoid-shaped: raw scores from about 0.31 to 0.66 all corresponded to about 65% positives.
- **Selective prediction / abstention:** act only above a threshold and report coverage vs. error rate.
- **Conformal prediction:** distribution-free guarantees on error rate, assuming exchangeable data.
- **Decision calibration:** calibrate specifically at the thresholds your decisions use, rather than everywhere.

### 4. The name collision

"RLCD: Reinforcement Learning from Contrastive Distillation for Language Model Alignment" (Yang, Klein, Celikyilmaz, Peng, Tian; arXiv 2307.12950; ICLR 2024) is unrelated. It builds preference pairs from two outputs, one prompted to follow a principle (e.g., harmlessness) and one prompted to violate it. It trains a preference model on those pairs and then does RL. It is essentially a cleaner RLAIF, and it has nothing to do with calibration. Hugging Face also already carries older checkpoints such as `TaylorAI/Llama-3B-RLCD-SFT` that use the older meaning. Many post-launch models tagged "RLCD" are not documented reproductions of TypeSafe's method.

### 5. Independent evidence on Jev's calibration (third-party measurements)

Almost all of this is on `jev-1.13.0`, run by individuals within two weeks of launch, without peer review. Read it as evidence to inspect, not settled fact.

| Study | Data | Result |
|---|---|---|
| Archer Hume | 1,200 MMLU items | Ten-bin ECE 0.0313; 990 of 1,200 predictions in the 0.9–1.0 bin; slightly overconfident at the top |
| scienthoon/jev-ood-calibration (summarized by Rajesh Beri, Sep 20) | 900 freshly generated synthetic support tickets + 3 public sets | ECE 0.107, 4.4× the 0.024 noise floor; public benchmarks 0.024–0.032 (possible contamination); Noul underconfident, Choice/Score overconfident; on a rule not present in the ticket text, 44.7% accuracy at 0.74 mean probability |
| Anthus (Ryan Porter) | 8,801 labeled sentiment examples | Noul stated 79.0% vs. 72.3% actual; Choice 91.4% vs. 76.1%; Choice accuracy 50–57% in every bucket below 95%; isotonic cut ECE 0.117 → 0.008; AUROC 0.83 vs. 0.72 for Llama 3.1-8B log-probs |
| TrueStandard | 108 hand-labeled grounding claims | ECE 0.066 (Jev) vs. 0.061 (Gemini 3.1 Flash Lite) vs. 0.067 (Claude Haiku 4.5), a statistical tie; Jev best Brier (0.0331) and best adversarial-tier accuracy (91.7% vs. 83.3%/80.6%) |
| jourdanlabs/assay-001 | CLINC150, Banking77 | ECE 0.020 vs. 0.094 on two similar intent tasks |
| jev-certify | CLINC150 conformal thresholds | 56.4% of answers at exactly 1.0 confidence, nine of them wrong, so the achievable risk bound floors at 1.95% |
| jujumilk3 audit | KoBBQ | Removing the abstain option took accuracy 0.950 → 0.000 and ECE 0.023 → 0.793 |

**What this means.** Jev's probabilities are genuinely *informative*: they rank right above wrong well, and Jev was rarely confidently wrong in TrueStandard's hard tier. But they are not uniformly *calibrated*. The sign of the error flips by question type (Noul under-, Choice over-confident). Calibration degrades on out-of-distribution rules and non-English input. And a properly prompted cheap LLM can match Jev's ECE on some tasks. The vendor claim "calibrated" is best read as "calibrated on the training distribution, approximately," not as a guarantee for your data.

**Probability vs. confidence, precisely.**
- `probabilities`: the per-option distribution (Choice), per-level distribution (Score), or a single P(true) (Noul). These are the numbers to calibrate.
- `confidence`: the peakedness of that distribution, not P(correct). For two options it equals 2·p_top − 1, so a 0.72 top probability gives 0.44 confidence. The separate confidence field was reported to be never better than the max probability.
- Probabilities are rounded to two decimals, which creates ties at 0.00/1.00 and limits fine thresholding.
- Related questions are not logically consistent. TypeSafe's jaggedness page shows a Noul and its negation summing to 1.19, and audits found a range of 0.71–1.42.

## Recommendations (for NAND eMMC/UFS failure analysis and ISO 26262 document review)

1. **Treat Jev as an uncalibrated scorer until proven otherwise on your data.** Label a few hundred historical cases, including the ambiguous ones. For eMMC/UFS, that means FA reports and device health logs with confirmed root cause. For ISO 26262, it means review findings with adjudicated outcomes. Anthus found a few hundred labeled examples captured most of the benefit, with isotonic beating Platt from 20 examples upward, but warned that below about 50 examples one unlucky draw can be worse than not calibrating.
2. **Measure three things, per question:**
   - A **reliability diagram** (10 bins of stated probability vs. observed frequency).
   - **ECE**, reported against its noise floor: at n = 60 a perfect model still scores ≈0.045.
   - The **Brier score**, which also rewards discrimination.
   - Also report accuracy-vs-coverage at your candidate thresholds, and hold out a test split that is never used to fit the calibrator or pick thresholds.
3. **Fit isotonic regression on the `probabilities`, not the `confidence` field**, then set thresholds in calibrated terms. "Auto-accept above 0.95 calibrated" then means about 95% of accepted cases are right *on that distribution*.
4. **Always include an explicit "unknown / insufficient evidence" option.** Without one, Jev answers anyway: in one pre-registered evaluation (5,721 calls), 0 of 30 out-of-scope messages were flagged, at 0.99 confidence. For failure modes, a sensible option set might be retention/read-disturb, P/E wear-out, FTL/firmware, controller/electrical overstress, board-level/solder, and "insufficient evidence."
5. **Do arithmetic in code, not in the model.** TypeSafe's own jaggedness page lists weakness at arithmetic and counting, and says the model reads dates as text, not as ordered quantities. Pre-compute health-log quantities (erase-count trends, spare-block depletion, eMMC EXT_CSD life-time/pre-EOL fields or UFS health descriptor values, time deltas) and pass Jev the conclusions as structured state.
6. **Decompose.** In one phishing study of 2,000 emails, a single "is this phishing?" question scored 62.6% (Haiku 81.3%). Five narrow signal questions combined in code with a logistic regression reached 95.0% (Haiku 93.2%), though that final gap was not statistically significant (p = 0.063). Ask "Does the report describe charge loss after high-temperature storage?" rather than "What is the failure mode?"
7. **Re-validate thresholds whenever anything changes: model version, question wording, option set, input language or source.** In Anthus's tests, rewording alone moved raw ECE between 0.064 and 0.160. Almeida has declined to promise long-term support for model versions. Pin `jev-1.13.0` explicitly and treat any version bump as a change requiring regression testing.
8. **For ISO 26262 contexts, keep Jev in an advisory or triage role unless you can qualify it.** Using an ML tool to review or check safety work products likely falls under software tool confidence and qualification (ISO 26262-8, clause 11: tool impact and tool error detection determine the tool confidence level), and ISO/PAS 8800 addresses AI in road vehicles. That is an assessment, not something TypeSafe addresses. A closed API with an unpublished training method and no long-term version support is hard to qualify. The defensible pattern is human review with Jev confidence used to *prioritize* reviewer attention, plus measured escape rates.
9. **Harden against injected text.** One study of 486 Wikipedia deletion discussions found a one-line injected instruction dropped accuracy from 96.5% to 26.5%, and supplier documents can contain text that reads like evidence. Also consider whether sending FA reports or safety cases to an external API is acceptable under your confidentiality obligations.

## Caveats

- **Vendor vs. verified vs. speculative:** everything about RLCD's *mechanism* in this report (proper scoring rules, known-probability synthetic data, classifier-like training) is informed speculation. TypeSafe has confirmed only the objective, the synthetic data, and that no paper exists yet.
- **Launch-post FAQ text** was quoted secondhand and could not be rendered directly. Verify it against the live page.
- **Community studies** are small, mostly single runs, rarely have confidence intervals, and sometimes disagree (MMLU ECE 0.031 vs. OOD ECE 0.107). Some disagreement likely reflects benchmark contamination and task mix. TrueStandard's result reversed twice as its sample grew from 22 to 108 claims.
- **Secondary explainers** (aiwiki, systemonemodels.org, various blogs) appear partly AI-assisted and sometimes state guesses as fact. For example, one blog asserts that RLCD uses proper scoring rules such as the Brier score, which TypeSafe has never said.
- **Things will change quickly:** new Jev versions, a possible RLCD paper, and more audits could supersede these findings within weeks.

## Key sources

- TypeSafe AI, "Introducing System One Models & Jev" (typesafe.ai/blog), Sep 15, 2026
- TypeSafe docs: AI primer, Confidence, Model jaggedness (docs.typesafe.ai)
- TechCrunch, "A new kind of AI model from a ChatGPT inventor is thrilling developers," Sep 18, 2026
- Latent Space, "Jev: System One models for Prod, not God," Sep 21, 2026
- systemonemodels.org, "RLCD explained"
- Anthus, "Can You Trust Jev's Confidence?" (anth.us)
- TrueStandard, "Jev Accuracy Tested: 108 Claims Across Three Models"
- GitHub: Yifan-Lan/awesome-jev-robustness; scienthoon/jev-ood-calibration; jujumilk3/jev-calibration-audit
- Damani et al., "Beyond Binary Rewards" (arXiv 2507.16806)
- Bani-Harouni, Stangel et al., "Rewarding Doubt" (arXiv 2503.02623)
- Tian et al., "Just Ask for Calibration" (arXiv 2305.14975)
- OpenAI, GPT-4 Technical Report (arXiv 2303.08774)
- Yang et al., "RLCD: Reinforcement Learning from Contrastive Distillation" (arXiv 2307.12950)

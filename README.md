# LLM with Lean4 Server Feedback

我使用了 Deepseek 提供的两个大模型，Deepseek-V3 和 Deepseek-R1，进行了测试。
将 miniF2F 中的 244 个问题，全部交给这两个模型进行解答。将答案反馈给 Lean4 Server 进行验证，并且不断返回错误信息。
最终 Deepseek-V3 的正确率是 17.84%，Deepseek-R1 的正确率是 40.98%。

在编写这个交互脚本的时候，会碰到两种情况：回答没有遵循约定的格式；回答不正确。
这两种情况正好对应 Deepseek-R1 技术报告中的奖励情况。
我直觉上觉得 Deepseek-R1 的奖励机制是一个多轮的对话游戏，和当前开源的复现版本 Open-R1 和 Simple-Reason 不太一样。 Claude 也可能使用的是 Code Server 多轮对话游戏的方式来增强模型的代码能力。

我觉得可能只需要构建一系列高效的对话游戏系统，用强化学习进行大模型的数学推理和代码能力的训练，效果就会非常好。这会不会是一种水下的其实大家都在做的事情呢？

## Result 


| Model | Success | Total | Rate |
| ----- | ------- | ---- | ---- |
| Deepseek-V3 | 43 | 244 | 17.84% |
| Deepseek-R1 | 100 | 244 | 40.98% |

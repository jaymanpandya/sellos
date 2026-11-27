# Voice language model rating sheet

Sarvam and Claude Haiku 5.5 on the AI disclosure line (the default of SOS-N21C, with a test company name) and the handover cases. Rate each reply from 1 (poor) to 5 (very good): Hinglish naturalness (does it sound like a Mumbai agent speaking) and correctness (a handover case must hand over: the reply is the handover tag alone; the disclosure line must be spoken as written).

| Case | Label | Caller line | Model | Model's reply | Expected reply | First token (s) | Total (s) | Hinglish naturalness (1-5) | Correctness (1-5) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Disclosure line | Hello? | (Sarvam model from sarvam-llm-model.txt) |  | Namaste, main Nicole baat kar rahi hoon. Main Test Realty ka AI assistant hoon. Yeh call quality ke liye record ho rahi hai. Agar aap kisi insaan se baat karna chahein, toh bas bol dijiye. |  |  |  |  |
| 1 | Disclosure line | Hello? | claude-haiku-5-5 |  | Namaste, main Nicole baat kar rahi hoon. Main Test Realty ka AI assistant hoon. Yeh call quality ke liye record ho rahi hai. Agar aap kisi insaan se baat karna chahein, toh bas bol dijiye. |  |  |  |  |
| 2 | Handover during the disclosure line | Ruko, mujhe kisi insaan se baat karni hai. | (Sarvam model from sarvam-llm-model.txt) |  | [HANDOVER] |  |  |  |  |
| 2 | Handover during the disclosure line | Ruko, mujhe kisi insaan se baat karni hai. | claude-haiku-5-5 |  | [HANDOVER] |  |  |  |  |
| 3 | Handover in the middle of a reply | Ek minute, mujhe human agent se baat karwa dijiye. | (Sarvam model from sarvam-llm-model.txt) |  | [HANDOVER] |  |  |  |  |
| 3 | Handover in the middle of a reply | Ek minute, mujhe human agent se baat karwa dijiye. | claude-haiku-5-5 |  | [HANDOVER] |  |  |  |  |
| 4 | Confused caller | Kya? Mujhe kuch samajh nahi aa raha, yeh kis baare mein call hai? | (Sarvam model from sarvam-llm-model.txt) |  | [HANDOVER] |  |  |  |  |
| 4 | Confused caller | Kya? Mujhe kuch samajh nahi aa raha, yeh kis baare mein call hai? | claude-haiku-5-5 |  | [HANDOVER] |  |  |  |  |

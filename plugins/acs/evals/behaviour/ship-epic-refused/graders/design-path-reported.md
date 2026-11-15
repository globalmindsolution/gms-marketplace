---
type: regex
target: last_message
pattern: 'create-tech-design[\s\S]*breakdown-ticket|breakdown-ticket[\s\S]*create-tech-design'
flags: i
---

ship surfaces the brake's pointer: settle the design with
`/acs:create-tech-design EVAL-1`, then mint the children with `/acs:breakdown-ticket EVAL-1`,
then ship each child. A reply naming only one half, or neither, is not the
pointer.

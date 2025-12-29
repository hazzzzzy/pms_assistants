```shell
uvicorn main:app --reload --host 0.0.0.0 --port 8866
```

```shell
uvicorn main:app  --host 0.0.0.0 --port 8866 --workers 2
```

### 待完成

- [ ] 上下文记忆功能
- [ ] 聊天历史存储
- [ ] 用户反馈
- [ ] 智能体判断
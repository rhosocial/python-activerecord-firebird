# rhosocial-activerecord Firebird 后端文档（中文）

> 📖 **参见**：[核心库文档](https://github.com/rhosocial/python-activerecord/tree/main/docs/en_US)
> 与[英文版后端文档](../en_US/README.md)。

本文档只覆盖**本后端特有的内容**，不重复核心库的 ActiveRecord、查询或迁移体系。

> ⚠️ **仅支持同步。** `firebird-driver` 没有原生异步 API。`AsyncFirebirdBackend` 只是为保持
> API 形状一致而保留的线程池包装，**不建议用于生产**。生产负载请使用同步的 `FirebirdBackend`。

## 目录

1. **[简介](../en_US/introduction/README.md)**
      * **[概述](../en_US/introduction/README.md)**
      * **[支持的版本](../en_US/introduction/supported_versions.md)**
      * **[能力门控与快速失败](../en_US/introduction/capability_gates.md)**

2. **[安装](../en_US/installation/README.md)**
      * **[安装指南](../en_US/installation/installation.md)**
      * **[连接配置](../en_US/installation/configuration.md)**

3. **[模型定义](../en_US/modeling/README.md)**
      * **[Firebird 字段类型与方言](../en_US/modeling/field_types.md)**

4. **[查询](../en_US/querying/README.md)**
      * **[日期/时间差异：`seconds_between`](../en_US/querying/seconds_between.md)**

5. **[DDL](../en_US/ddl/README.md)**
      * **[域、生成器与例程](../en_US/ddl/domains_generators_routines.md)**

6. **[事务](../en_US/transactions/README.md)**
      * **[事务与保存点](../en_US/transactions/README.md)**

7. **[自省](../en_US/introspection/README.md)**
      * **[数据库自省](../en_US/introspection/README.md)**

8. **[命令行](../en_US/cli/README.md)**
      * **[CLI 用法](../en_US/cli/README.md)**

9. **[迁移](migration/README.md)**
      * **[在 Firebird 后端上运行迁移](migration/README.md)**：配置、事务性 DDL、方言/版本门控、同步的函数式与 `named-migration` 接线

10. **[测试](../en_US/testing/README.md)**
      * **[测试配置](../en_US/testing/README.md)**

11. **[可运行示例](../examples/README.md)**
      * **[connection.py](../examples/connection.py)**
      * **[ddl.py](../examples/ddl.py)**
      * **[introspection.py](../examples/introspection.py)**
      * **[迁移示例](../examples/migration/README.md)**

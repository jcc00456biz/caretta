# caretta

Java/Pythonのソースコードを解析し、クラス・フィールド・メソッドの説明とMermaidクラス図を含むMarkdownを生成するCLIツールです。

## セットアップ

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## 使い方

```powershell
python src\caretta\caretta.py path\to\Source.java
python src\caretta\caretta.py path\to\module.py --output docs\module.md
python src\caretta\caretta.py path\to\source-directory -o documentation.md
```

ファイルを指定するとそのファイルを、ディレクトリを指定すると配下の `.java` / `.py` ファイルを解析します。出力にはソースに記述されたコメントやdocstringを説明として利用し、説明コメントのないメソッドは参照フィールドと実装コードを併記します。出力先を省略した場合はカレントディレクトリの `documentation.md` に保存します。

## VS Code でデバッグ実行

`.vscode/launch.json` の「caretta: Java サンプルを解析」を選んでデバッグを開始すると、`run_dir` をカレントディレクトリとして `Sample.java` を解析し、結果を `run_dir/documentation.md` に出力します。

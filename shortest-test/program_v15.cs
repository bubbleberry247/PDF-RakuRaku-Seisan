class Program

{

static Program()

{

System.Globalization.CultureInfo.CurrentCulture = new System.Globalization.CultureInfo(Keyence.Activities.EnvironmentVariableAccessor.CultureName);

System.Globalization.CultureInfo.CurrentUICulture = new System.Globalization.CultureInfo(Keyence.Activities.EnvironmentVariableAccessor.CultureName);

System.Globalization.CultureInfo.DefaultThreadCurrentCulture = new System.Globalization.CultureInfo(Keyence.Activities.EnvironmentVariableAccessor.CultureName);

System.Globalization.CultureInfo.DefaultThreadCurrentUICulture = new System.Globalization.CultureInfo(Keyence.Activities.EnvironmentVariableAccessor.CultureName);

}



    [System.STAThread]

    public static void Main()

    {

        Keyence.CommentActions.CommentScopeAction.BeginComment("56abb5c3-1d2f-4099-9e6a-432f3370d03e", $@"実行環境判定");

        var EnvFilePath = $@"..\config\env.txt";

        var Env = Keyence.FileSystemActions.FileAction.ReadAllText(EnvFilePath, Keyence.Encodings.ReadEncodingType.Auto);

        Env = Keyence.TextActions.TextAction.TrimText(Env, Keyence.TextActions.WhatToTrim.Both);

        Env = Keyence.TextActions.TextAction.ChangeTextCase(Env, Keyence.TextActions.TextConvertStyle.UpperCase);

        Keyence.CommentActions.LogAction.OutputUserLog(Env);

        var ConfigPath = "";

        if (Keyence.ComparisonActions.ComparisonAction.CompareString(Env, $@"PROD", Keyence.ComparisonActions.StringComparingOperator.Equal, false))

        {

            ConfigPath = "..\\config\\RK10_config_PROD.xlsx";

        }

        else if (Keyence.ComparisonActions.ComparisonAction.CompareString(Env, $@"PROD", Keyence.ComparisonActions.StringComparingOperator.NotEqual, false))

        {

            ConfigPath = "..\\config\\RK10_config_LOCAL.xlsx";

            Keyence.CommentActions.LogAction.OutputUserLog(ConfigPath);

        }



        Keyence.CommentActions.CommentScopeAction.EndComment("56abb5c3-1d2f-4099-9e6a-432f3370d03e");

        Keyence.CommentActions.CommentScopeAction.BeginComment("00be799c-7939-4106-ad6a-6d786aa81aa5", $@"Config読込（Excel→変数展開）");

        var exce1 = Keyence.ExcelActions.ExcelAction.OpenFileAndReturnPath(ConfigPath, false, "", true, "", true, true);

        var cfg_ENV = Keyence.ExcelActions.ExcelAction.GetCellValue(Keyence.ExcelActions.RangeSpecificationMethod.A1, 1, 1, $@"B2", Keyence.ExcelActions.TableCellValueMode.String);

        var ROOT_TIC_MAIN = Keyence.ExcelActions.ExcelAction.GetCellValue(Keyence.ExcelActions.RangeSpecificationMethod.A1, 1, 1, $@"B3", Keyence.ExcelActions.TableCellValueMode.String);

        var KUMIAI_DIR = Keyence.ExcelActions.ExcelAction.GetCellValue(Keyence.ExcelActions.RangeSpecificationMethod.A1, 1, 1, $@"B4", Keyence.ExcelActions.TableCellValueMode.String);

        var KUMIAI_DATA_DIR = Keyence.ExcelActions.ExcelAction.GetCellValue(Keyence.ExcelActions.RangeSpecificationMethod.A1, 1, 1, $@"B5", Keyence.ExcelActions.TableCellValueMode.String);

        var ETC_ORIGINAL_XLSX = Keyence.ExcelActions.ExcelAction.GetCellValue(Keyence.ExcelActions.RangeSpecificationMethod.A1, 1, 1, $@"B6", Keyence.ExcelActions.TableCellValueMode.String);

        var KEIRI_KEIEI_DIR = Keyence.ExcelActions.ExcelAction.GetCellValue(Keyence.ExcelActions.RangeSpecificationMethod.A1, 1, 1, $@"B8", Keyence.ExcelActions.TableCellValueMode.String);

        var PDF_OUT_DIR = Keyence.ExcelActions.ExcelAction.GetCellValue(Keyence.ExcelActions.RangeSpecificationMethod.A1, 1, 1, $@"B10", Keyence.ExcelActions.TableCellValueMode.String);

        var SENARIO_DIR = Keyence.ExcelActions.ExcelAction.GetCellValue(Keyence.ExcelActions.RangeSpecificationMethod.A1, 1, 1, $@"B11", Keyence.ExcelActions.TableCellValueMode.String);

        var ROBOT43 = Keyence.ExcelActions.ExcelAction.GetCellValue(Keyence.ExcelActions.RangeSpecificationMethod.A1, 1, 1, $@"B12", Keyence.ExcelActions.TableCellValueMode.String);

        var PDF_IN_DIR = Keyence.ExcelActions.ExcelAction.GetCellValue(Keyence.ExcelActions.RangeSpecificationMethod.A1, 1, 1, $@"B14", Keyence.ExcelActions.TableCellValueMode.String);

        var 日本高速情報センターWEB = Keyence.ExcelActions.ExcelAction.GetCellValue(Keyence.ExcelActions.RangeSpecificationMethod.A1, 1, 1, $@"B15", Keyence.ExcelActions.TableCellValueMode.String);

        var 解凍フォルダ_CSV＿DIR = Keyence.ExcelActions.ExcelAction.GetCellValue(Keyence.ExcelActions.RangeSpecificationMethod.A1, 1, 1, $@"B16", Keyence.ExcelActions.TableCellValueMode.String);

        var 解凍フォルダ_PDF＿DIR = Keyence.ExcelActions.ExcelAction.GetCellValue(Keyence.ExcelActions.RangeSpecificationMethod.A1, 1, 1, $@"B17", Keyence.ExcelActions.TableCellValueMode.String);

        var Temp1 = Keyence.ExcelActions.ExcelAction.GetCellValue(Keyence.ExcelActions.RangeSpecificationMethod.A1, 1, 1, $@"B18", Keyence.ExcelActions.TableCellValueMode.String);

        var RAKURAKUSEISAN_WEB = Keyence.ExcelActions.ExcelAction.GetCellValue(Keyence.ExcelActions.RangeSpecificationMethod.A1, 1, 1, $@"B13", Keyence.ExcelActions.TableCellValueMode.String);

        var メールアドレス = Keyence.ExcelActions.ExcelAction.GetCellValue(Keyence.ExcelActions.RangeSpecificationMethod.A1, 1, 1, $@"B22", Keyence.ExcelActions.TableCellValueMode.String);

        var MAIL_SUBJECT_PREFIX = Keyence.ExcelActions.ExcelAction.GetCellValue(Keyence.ExcelActions.RangeSpecificationMethod.A1, 1, 1, $@"B23", Keyence.ExcelActions.TableCellValueMode.String);

        var MAIL_BODY_TEMPLATE = Keyence.ExcelActions.ExcelAction.GetCellValue(Keyence.ExcelActions.RangeSpecificationMethod.A1, 1, 1, $@"B24", Keyence.ExcelActions.TableCellValueMode.String);

        if (Keyence.ComparisonActions.ComparisonAction.CompareString(cfg_ENV, Env, Keyence.ComparisonActions.StringComparingOperator.NotEqual, false))

        {

            Keyence.CommentActions.LogAction.OutputUserLog(Env);

            Keyence.CommentActions.LogAction.OutputUserLog(cfg_ENV);

        }



        Keyence.CommentActions.CommentScopeAction.EndComment("00be799c-7939-4106-ad6a-6d786aa81aa5");

        Keyence.ExcelActions.ExcelAction.CloseFile();

        Keyence.CommentActions.CommentScopeAction.BeginComment("685bc8f3-268a-4a96-8eee-badb4c390523", $@"ログイン");

        var webController1 = Keyence.WebActions.WebAction.StartEdgeWithEngineSelection($@"{日本高速情報センターWEB}", false, true, 90, new System.Collections.Generic.List<string> { }, false, 3d);

        Keyence.WebActions.WebAction.SetWindowPosition(webController1, 71, 0, 1601, 1000);

        // ログイン処理（画像認識をスキップして常に実行）
        Keyence.ThreadingActions.ThreadingAction.Wait(10d);

        Keyence.WebActions.WebSingleHtmlElementAction.ClickMouseLeft(webController1, Keyence.WebActions.WebSingleHtmlElementAction.CreateSelector(Keyence.WebActions.SyntaxType.Xpath, "//input[@type='text']", "#root#"), Keyence.WebActions.MouseClickActionType.Click, 0, 0, 90, false);

        var string1 = Keyence.SystemActions.SystemAction.ReadPasswordFromCredential("ログインID　ETC");

        Keyence.WebActions.WebSingleHtmlElementAction.InputTextField(webController1, Keyence.WebActions.WebSingleHtmlElementAction.CreateSelector(Keyence.WebActions.SyntaxType.Xpath, "//input[@type='text']", "#root#"), string1, true, 0, 0, 0, true);

        Keyence.WebActions.WebSingleHtmlElementAction.ClickMouseLeft(webController1, Keyence.WebActions.WebSingleHtmlElementAction.CreateSelector(Keyence.WebActions.SyntaxType.Xpath, "//input[@type='password']", "#root#"), Keyence.WebActions.MouseClickActionType.Click, 0, 0, 90, false);

        var string2 = Keyence.SystemActions.SystemAction.ReadPasswordFromCredential("パスワード　ETC");

        Keyence.WebActions.WebSingleHtmlElementAction.InputTextField(webController1, Keyence.WebActions.WebSingleHtmlElementAction.CreateSelector(Keyence.WebActions.SyntaxType.Xpath, "//input[@type='password']", "#root#"), string2, true, 0, 0, 0, true);

        Keyence.WebActions.WebSingleHtmlElementAction.ClickMouseLeft(webController1, Keyence.WebActions.WebSingleHtmlElementAction.CreateSelector(Keyence.WebActions.SyntaxType.Xpath, "//button[@type='submit']", "#root#"), Keyence.WebActions.MouseClickActionType.Click, 0, 0, 90, false);



        Keyence.CommentActions.CommentScopeAction.EndComment("685bc8f3-268a-4a96-8eee-badb4c390523");

        Keyence.CommentActions.CommentScopeAction.BeginComment("9607f7ab-3365-4ee0-84e9-731c63090b68", $@"ZIPダウンロード");

        Keyence.ThreadingActions.ThreadingAction.Wait(15d);


        Keyence.WebActions.WebAction.GoToUrl(webController1, "https://rbbrier.eco-serv.jp/etc/mypage/", true, 90, false);

        Keyence.ThreadingActions.ThreadingAction.Wait(5d);
        Keyence.WebActions.WebSingleHtmlElementAction.ClickMouseLeft(webController1, Keyence.WebActions.WebSingleHtmlElementAction.CreateSelector(Keyence.WebActions.SyntaxType.Xpath, "//a[contains(.,'.zip')]", "#root#"), Keyence.WebActions.MouseClickActionType.Click, 0, 0, 90, false);

        Keyence.ThreadingActions.ThreadingAction.Wait(10d);

        Keyence.WebActions.WebSingleHtmlElementAction.ClickMouseLeft(webController1, Keyence.WebActions.WebSingleHtmlElementAction.CreateSelector(Keyence.WebActions.SyntaxType.Xpath, "//a/div/div/p", "#root#"), Keyence.WebActions.MouseClickActionType.Click, 0, 0, 90, false);

        Keyence.ThreadingActions.ThreadingAction.Wait(18d);

        Keyence.UIActions.XPathElementAction.WaitUiElementByProcessNameAndXPath("msedge.exe", "/Pane[2]/Pane[2]/Window[1]/Pane[1]/Pane[1]/Pane[2]/Pane[1]/Document[1]/Button[1]", true, 30d, false);

        Keyence.WebActions.WebAction.GoToUrl(webController1, "https://rbbrier.eco-serv.jp/etc/mypage/bapPublishedBillAppSearch", true, 90, false);

        Keyence.WebActions.WebAction.SetWindowPosition(webController1, 71, 0, 1600, 1000);

        Keyence.UIActions.KeyboardAction.SendKey("J", Keyence.UIActions.ModifierKeysType.Ctrl, 1d);

        Keyence.UIActions.KeyboardAction.SendKeyRepeatedly("Tab", Keyence.UIActions.ModifierKeysType.None, 10, 0.2d);

        Keyence.UIActions.KeyboardAction.SendKey("Enter", Keyence.UIActions.ModifierKeysType.None, 0.1d);

        Keyence.ThreadingActions.ThreadingAction.Wait(10d);

        Keyence.WebActions.WebAction.EndBrowser(webController1);

        Keyence.CommentActions.CommentScopeAction.EndComment("9607f7ab-3365-4ee0-84e9-731c63090b68");

        Keyence.CommentActions.CommentScopeAction.BeginComment("426eb9b0-968e-4789-83c2-a1a6dbc402da", $@"Zipファイル展開");

        var ダウンロードフォルダ = Keyence.FileSystemActions.DirectoryAction.GetSpecificDirectory(Keyence.FileSystemActions.SpecialDirectory.Download);

        var string11 = Keyence.FileSystemActions.DirectoryAction.GetNewestFilePath(ダウンロードフォルダ, $@"11278_11278_東海インプル建設㈱_*.zip", Keyence.FileSystemLib.FileSystemInfoFilter.CreateEmpty(), true);

        var string12 = Keyence.FileSystemActions.FileAction.GetFileNameWithoutExtension(string11);

        var list1 = Keyence.TextActions.TextAction.SplitText(string12, true, Keyence.TextActions.DelimiterType.Space, 1, $@"_", false);

        var 使用月仮 = Keyence.ListActions.ListAction.GetItem(list1, 3);

        var 使用月 = Keyence.TextActions.TextAction.GetSubText(使用月仮, Keyence.TextActions.StartIndexType.CharacterPosition, 0, Keyence.TextActions.EndLengthType.NumberOfChars, Keyence.NumericActions.NumericAction.ConvertFromObjectToInteger(6d));

        var 使用月日 = Keyence.DateTimeActions.DateTimeAction.AddDatetime(Keyence.TextActions.TextAction.ConvertFromTextToDatetime($@"{使用月}01", true, $@"yyyyMMdd"), 1, Keyence.DateTimeActions.TimeUnit.Month);

        var string10 = Keyence.TextActions.TextAction.ConvertFromDatetimeToText(使用月日, true, Keyence.TextActions.DateTimeFormat.ShortDate, $@"yyyyMM");

        Keyence.ThreadingActions.ThreadingAction.Wait(2d);

        var 解凍フォルダ = Keyence.FileSystemActions.DirectoryAction.CreateDirectory(ダウンロードフォルダ, $@"11278_11278_東海インプル建設㈱_{使用月}");

        Keyence.ThreadingActions.ThreadingAction.Wait(7d);

        var UnzipOK = false;

        foreach (var カウンター1 in Keyence.Activities.Samples.RepeatExtensions.RepeatCount(10))

        {

            try

            {

                Keyence.FileSystemActions.CompressionAction.UncompressFile(string11, 解凍フォルダ, true, "", Keyence.FileSystemActions.EncodingType.ShiftJis);

                UnzipOK = true;

                break;

            }

            catch (System.Exception エラー1)when (エラー1 is not Keyence.Activities.Exceptions.ForceExitException)

            {

                Keyence.ThreadingActions.ThreadingAction.Wait(2d);

            }

        }



        if (Keyence.Activities.Samples.VariableAction.InvertBool(UnzipOK))

        {

            Keyence.CommentActions.LogAction.OutputUserLog($@"ZIP展開が10回失敗。解凍先のCSV/PDFが開かれていないか確認してください。");

            return;

        }



        Keyence.CommentActions.CommentScopeAction.EndComment("426eb9b0-968e-4789-83c2-a1a6dbc402da");

        Keyence.CommentActions.CommentScopeAction.BeginComment("a86181a1-7a3c-41fb-967d-7edae540aa34", $@"明細転記作業");

        var Tempフォルダ作成 = Keyence.FileSystemActions.DirectoryAction.CreateDirectory($@"{ROBOT43}", $@"Temp");

        Keyence.CommentActions.CommentScopeAction.BeginComment("c28c6b93-809b-473a-ada4-22edd1c8e62f", $@"原本転記");

        Keyence.ThreadingActions.ThreadingAction.Wait(2d);

        var string7 = Keyence.FileSystemActions.DirectoryAction.GetNewestFilePath($@"{解凍フォルダ}{解凍フォルダ_CSV＿DIR}", $@"{使用月}-500法人カード別明細*", Keyence.FileSystemLib.FileSystemInfoFilter.CreateEmpty(), true);

        Keyence.ThreadingActions.ThreadingAction.Wait(2d);

        var string13 = Keyence.FileSystemActions.DirectoryAction.GetNewestFilePath($@"{KUMIAI_DIR}", "*", Keyence.FileSystemLib.FileSystemInfoFilter.CreateEmpty(), true);

        var 法人カード別明細 = Keyence.SpreadDataActions.SpreadDataAction.ConvertExcelToDataTable(string7, null, new System.Collections.Generic.List<string> { "*" });

        var string8 = Keyence.FileSystemActions.DirectoryAction.GetNewestFilePath(ダウンロードフォルダ, $@"*東海インプル建設*", Keyence.FileSystemLib.FileSystemInfoFilter.CreateEmpty(), true);

        var カード利用料原本 = Keyence.ExcelActions.ExcelAction.OpenFileAndReturnPath(ETC_ORIGINAL_XLSX, false, "", true, "", true, true);

        Keyence.ExcelActions.ExcelAction.SelectSheet(Keyence.ExcelActions.SheetSelectionMode.Name, "カード別明細（割引）", 1);

        Keyence.ExcelActions.ExcelAction.WriteCell(Keyence.ExcelActions.RangeSpecificationMethod.A1, Keyence.ExcelActions.CellSelectionMethod.Specified, 1, 1, $@"A2", Keyence.ExcelActions.InputValueType.Table, "", 法人カード別明細, default, false, false);

        var string9 = Keyence.FileSystemActions.DirectoryAction.GetNewestFilePath($@"{解凍フォルダ}{解凍フォルダ_CSV＿DIR}", $@"*法人通行明細*.csv", Keyence.FileSystemLib.FileSystemInfoFilter.CreateEmpty(), true);

        var 法人通行明細 = Keyence.SpreadDataActions.SpreadDataAction.ConvertExcelToDataTable(string9, null, new System.Collections.Generic.List<string> { "*" });

        Keyence.ThreadingActions.ThreadingAction.Wait(4d);

        var TargetSheet = 使用月;

        Keyence.UIActions.KeyboardAction.SendKey("Escape", Keyence.UIActions.ModifierKeysType.None, 0.5d);

        Keyence.ExcelActions.ExcelAction.ActivateFile($@"{カード利用料原本}", true);

        Keyence.ExcelActions.ExcelAction.SelectSheet(Keyence.ExcelActions.SheetSelectionMode.Name, $@"{string10}", 1);

        Keyence.ExcelActions.ExcelAction.WriteCell(Keyence.ExcelActions.RangeSpecificationMethod.A1, Keyence.ExcelActions.CellSelectionMethod.Specified, 1, 1, $@"A5", Keyence.ExcelActions.InputValueType.Table, "", 法人通行明細, default, false, false);

        Keyence.CommentActions.CommentScopeAction.BeginComment("376a7e9a-869b-45a3-a599-d4b43a3ca475", $@"列幅拡張");

        Keyence.ExcelActions.ExcelAction.FilterRow(Keyence.ExcelActions.RangeSpecificationMethod.A1, Keyence.ExcelActions.RangeSelectionMethod.Single, 9, 3, 9, 3, $@"S4", $@"部署", Keyence.ExcelActions.FilterTypeSelectionMethod.Text, Keyence.ComparisonActions.StringComparingForExcelOperator.NotEqual, "", Keyence.ComparisonActions.NumberComparingForExcelOperator.Equal, 0d, Keyence.ComparisonActions.DateTimeComparingForExcelOperator.Equal, Keyence.Activities.Samples.VariableAction.CreateDateTime(2025, 12, 17, 16, 31, 36), Keyence.ExcelActions.AndOrSelectionMethod.And, Keyence.ComparisonActions.StringComparingForExcelOperator.Empty, "", Keyence.ComparisonActions.NumberComparingForExcelOperator.Empty, 0d, Keyence.ComparisonActions.DateTimeComparingForExcelOperator.Empty, Keyence.Activities.Samples.VariableAction.CreateDateTime(2025, 12, 17, 16, 31, 36));

        Keyence.ExcelActions.ExcelAction.FilterRow(Keyence.ExcelActions.RangeSpecificationMethod.A1, Keyence.ExcelActions.RangeSelectionMethod.Single, 1, 1, 1, 1, $@"L4", $@"利用金額", Keyence.ExcelActions.FilterTypeSelectionMethod.Numeric, Keyence.ComparisonActions.StringComparingForExcelOperator.Equal, "", Keyence.ComparisonActions.NumberComparingForExcelOperator.GreaterThan, 0d, Keyence.ComparisonActions.DateTimeComparingForExcelOperator.Equal, Keyence.Activities.Samples.VariableAction.CreateDateTime(2025, 12, 24, 10, 15, 49), Keyence.ExcelActions.AndOrSelectionMethod.And, Keyence.ComparisonActions.StringComparingForExcelOperator.Empty, "", Keyence.ComparisonActions.NumberComparingForExcelOperator.Empty, 0d, Keyence.ComparisonActions.DateTimeComparingForExcelOperator.Empty, Keyence.Activities.Samples.VariableAction.CreateDateTime(2025, 12, 24, 10, 15, 49));

        Keyence.UIActions.KeyboardAction.SendKey("Escape", Keyence.UIActions.ModifierKeysType.None, 0.5d);

        Keyence.UIActions.KeyboardAction.SendKey("F5", Keyence.UIActions.ModifierKeysType.None, 0.2d);

        Keyence.UIActions.KeyboardAction.TextEntry($@"F:F");

        Keyence.UIActions.KeyboardAction.SendKey("Enter", Keyence.UIActions.ModifierKeysType.None, 0.2d);

        Keyence.UIActions.KeyboardAction.SendKey("LMenu", Keyence.UIActions.ModifierKeysType.None, 0.1d);

        Keyence.UIActions.KeyboardAction.SendKey("H", Keyence.UIActions.ModifierKeysType.None, 0.1d);

        Keyence.UIActions.KeyboardAction.SendKey("O", Keyence.UIActions.ModifierKeysType.None, 0.1d);

        Keyence.UIActions.KeyboardAction.SendKey("I", Keyence.UIActions.ModifierKeysType.None, 0.2d);

        Keyence.CommentActions.CommentScopeAction.EndComment("376a7e9a-869b-45a3-a599-d4b43a3ca475");

        Keyence.CommentActions.CommentScopeAction.EndComment("c28c6b93-809b-473a-ada4-22edd1c8e62f");

        var string6 = Keyence.FileSystemActions.DirectoryAction.GetNewestFilePath($@"{ダウンロードフォルダ}\11278_11278_東海インプル建設㈱_{使用月}\PDF", "*", Keyence.FileSystemLib.FileSystemInfoFilter.CreateEmpty(), true);

        var 請求書PdfPath_抽出 = Keyence.FileSystemActions.DirectoryAction.GetNewestFilePath($@"{ダウンロードフォルダ}\11278_11278_東海インプル建設㈱_{使用月}\PDF", $@"*法人請求書*.pdf", Keyence.FileSystemLib.FileSystemInfoFilter.CreateEmpty(), true);

        var お支払日原文 = Keyence.PdfActions.PdfActions.ExtractText($@"{請求書PdfPath_抽出}", 1, 143, 308, 141, 13);

        Keyence.ExcelActions.ExcelAction.WriteCell(Keyence.ExcelActions.RangeSpecificationMethod.A1, Keyence.ExcelActions.CellSelectionMethod.Specified, 1, 1, $@"I3", Keyence.ExcelActions.InputValueType.String, Keyence.TextActions.TextAction.ConvertFromDatetimeToText(Keyence.TextActions.TextAction.ConvertFromTextToDatetime(お支払日原文, false, "yyyy/MM/dd H:mm:ss"), false, Keyence.TextActions.DateTimeFormat.ShortDate, "yyyy/MM/dd H:mm:ss"), default, default, false, false);

        var 部署計シート = Keyence.ExcelActions.ExcelAction.ExportPdf(Keyence.ExcelActions.PdfExportType.ActiveSheet, "", $@"{Temp1}\部署計シート.pdf", true);

        var 原本別名保存 = Keyence.ExcelActions.ExcelAction.SaveFile($@"{PDF_OUT_DIR}\ＥＴＣカード利用料_2025.原本tmp.xlsx", Keyence.ExcelActions.PreservationMethod.SaveAs, Keyence.ExcelActions.SaveFileType.ExtensionCompliant);

        Keyence.ExcelActions.ExcelAction.CloseFile();

        var 法人請求書 = Keyence.FileSystemActions.FileAction.CopyFileDirectory($@"{解凍フォルダ}\PDF\{使用月}-500法人請求書11278東海インプル建設㈱.pdf", $@"{PDF_IN_DIR}", true);

        Keyence.ThreadingActions.ThreadingAction.Wait(5d);

        Keyence.CommentActions.CommentScopeAction.BeginComment("cb18f4f9-4c6f-43ba-ad8b-0056c251ff7d", $@"請求額");

        var 請求書PdfPath = Keyence.FileSystemActions.DirectoryAction.GetNewestFilePath($@"{解凍フォルダ}\{解凍フォルダ_PDF＿DIR}", $@"{使用月}-500法人請求書*.pdf", Keyence.FileSystemLib.FileSystemInfoFilter.CreateEmpty(), true);

        var 請求書発行日tmp = Keyence.PdfActions.PdfActions.ExtractText(請求書PdfPath, 1, 479, 71, 97, 22);

        var 請求書発行日tmp2 = Keyence.TextActions.TextAction.ReplaceText(請求書発行日tmp, $@"発行", false, false, "", false, false);

        var 請求書発行日＿Trim = Keyence.TextActions.TextAction.TrimText(請求書発行日tmp2, Keyence.TextActions.WhatToTrim.Both);

        var 請求書発行日_dt = Keyence.TextActions.TextAction.ConvertFromTextToDatetime(請求書発行日＿Trim, true, $@"yyyy年MM月dd日");

        var 請求書発行月日_yyymmdd = Keyence.TextActions.TextAction.ConvertFromDatetimeToText(請求書発行日_dt, true, Keyence.TextActions.DateTimeFormat.ShortDate, $@"yyyyMMdd");

        var ご請求額原文 = Keyence.PdfActions.PdfActions.ExtractText(法人請求書, 1, 115, 275, 189, 18);

        var ご請求額tmp1 = Keyence.TextActions.TextAction.ReplaceText(ご請求額原文, $@",", false, false, "", false, false);

        var ご請求額tmp2 = Keyence.TextActions.TextAction.ReplaceText(ご請求額tmp1, $@"円", false, false, "", false, false);

        var ご請求額 = Keyence.TextActions.TextAction.TrimText(ご請求額tmp2, Keyence.TextActions.WhatToTrim.Both);

        Keyence.CommentActions.CommentScopeAction.EndComment("cb18f4f9-4c6f-43ba-ad8b-0056c251ff7d");

        Keyence.CommentActions.CommentScopeAction.BeginComment("f49f2367-b134-490a-8c20-1e591ea8cb2c", $@"申請用フォルダ作成");

        var 締年月 = Keyence.TextActions.TextAction.ConvertFromDatetimeToText(請求書発行日_dt, true, Keyence.TextActions.DateTimeFormat.ShortDate, $@"yyyy.MM");

        var string4 = Keyence.TextActions.TextAction.Concat(締年月, $@"月締分処理");

        var 申請用フォルダパスtmp1 = Keyence.TextActions.TextAction.Concat($@"{KEIRI_KEIEI_DIR}\", string4);

        var 申請用フォルダパスtmp2 = Keyence.TextActions.TextAction.Concat(申請用フォルダパスtmp1, $@"\申請用");

        var 申請フォルダ存在確認 = Keyence.FileSystemActions.DirectoryAction.DirectoryExists(申請用フォルダパスtmp2);

        if (Keyence.Activities.Samples.VariableAction.InvertBool(申請フォルダ存在確認))

        {

            var 申請用フォルダ作成 = Keyence.FileSystemActions.DirectoryAction.CreateDirectory(申請用フォルダパスtmp1, $@"申請用");

        }

        else

        {

        }



        Keyence.CommentActions.CommentScopeAction.EndComment("f49f2367-b134-490a-8c20-1e591ea8cb2c");

        Keyence.PdfActions.PdfActions.Merge(new System.Collections.Generic.List<string> { 部署計シート, 法人請求書 }, $@"{Temp1}\【申請用】日本情報サービス協同組合_{請求書発行月日_yyymmdd}_{ご請求額}tmp.pdf");

        var directoryState1 = Keyence.ThreadingActions.ThreadingAction.GetDirectoryState(PDF_OUT_DIR);

        Keyence.CommentActions.CommentScopeAction.EndComment("a86181a1-7a3c-41fb-967d-7edae540aa34");

        Keyence.CommentActions.CommentScopeAction.BeginComment("806c7c67-7744-4d4a-9aee-54c1dc0d82e3", $@"バッチファイル実行");

        Keyence.FileSystemActions.FileAction.OpenFile($@"{ROBOT43}\run_pdf_annotate_safe.bat");

        Keyence.CommentActions.CommentScopeAction.EndComment("806c7c67-7744-4d4a-9aee-54c1dc0d82e3");

        var 表1 = Keyence.ThreadingActions.ThreadingAction.GetSelectedStateFile(directoryState1, $@"【申請用】日本情報サービス協同組合_{請求書発行月日_yyymmdd}_{ご請求額}.pdf", Keyence.FileSystemLib.MonitoredFileState.Updated, 180d, 15d);

        Keyence.ThreadingActions.ThreadingAction.Wait(2d);

        foreach (var カウンター2 in Keyence.Activities.Samples.RepeatExtensions.RepeatCount(30))

        {

            try

            {

                var string5 = Keyence.FileSystemActions.FileAction.CopyFileDirectory($@"{Temp1}【申請用】日本情報サービス協同組合_{請求書発行月日_yyymmdd}_{ご請求額}.pdf", $@"{申請用フォルダパスtmp2}", true);

                var string3 = Keyence.FileSystemActions.FileAction.CopyFileDirectory($@"{Temp1}【申請用】日本情報サービス協同組合_{請求書発行月日_yyymmdd}_{ご請求額}.pdf", $@"{PDF_OUT_DIR}", true);

                var string14 = Keyence.FileSystemActions.DirectoryAction.MoveDirectory($@"{解凍フォルダ}", $@"{KUMIAI_DATA_DIR}", true);

                break;

            }

            catch (System.Exception エラー2)when (エラー2 is not Keyence.Activities.Exceptions.ForceExitException)

            {

            }

        }



        var string15 = Keyence.FileSystemActions.DirectoryAction.GetNewestFilePath($@"{PDF_IN_DIR}", "*", Keyence.FileSystemLib.FileSystemInfoFilter.CreateEmpty(), true);

        Keyence.FileSystemActions.FileAction.DeleteFile($@"{PDF_IN_DIR}\{TargetSheet}-500法人請求書11278東海インプル建設㈱.pdf", true);

        Keyence.CommentActions.CommentScopeAction.BeginComment("30710178-0c9e-45b6-9db5-65fa71f4223c", $@"Config読込（Excel→変数展開）");

        var exce2 = Keyence.ExcelActions.ExcelAction.OpenFileAndReturnPath($@"{ConfigPath}", false, "", true, "", true, true);

        Keyence.CommentActions.CommentScopeAction.BeginComment("347a658a-cecd-4c6d-b9a1-0cfe7e6047b2", $@"部署計金額取得");

        var foundRow = 0;

        var foundCount = 0;

        var row = 0;

        var 金額＿管理 = -1;

        var 金額＿営業 = -1;

        var 金額＿業務 = -1;

        var 金額＿技術 = -1;

        var 金額＿営繕 = -1;

        var cellR = $@"";

        var cellJ = "";

        var cellQ = "";

        var 部署名 = "";

        var 合計ラベル = "";

        var 取得金額＿str = "";

        var 取得金額＿int = 0;

        var 申請用PDF = Keyence.FileSystemActions.DirectoryAction.GetNewestFilePath(PDF_OUT_DIR, $@"【申請用】日本情報サービス協同組合*.pdf", Keyence.FileSystemLib.FileSystemInfoFilter.CreateEmpty(), true);

        var string17 = Keyence.FileSystemActions.DirectoryAction.GetNewestFilePath(PDF_OUT_DIR, $@"ＥＴＣカード利用料_*.原本tmp.xlsx", Keyence.FileSystemLib.FileSystemInfoFilter.CreateEmpty(), true);

        var string18 = Keyence.ExcelActions.ExcelAction.OpenFileWithSelectionModeAndReturnPath(string17, Keyence.ExcelActions.FileOpenSelectionMode.Default, "", true, "", true, true);

        Keyence.ExcelActions.ExcelAction.SelectSheet(Keyence.ExcelActions.SheetSelectionMode.Name, $@"{string10}", 1);

        var list2 = Keyence.ExcelActions.ExcelAction.GetMatchValueList(Keyence.ExcelActions.RangeSpecificationMethod.A1, 1, 1, 1, 1, $@"j:j", $@"総合計", false);

        cellJ = Keyence.ListActions.ListAction.GetItem(list2, 0);

        cellJ = Keyence.TextActions.TextAction.ReplaceText(cellJ, $@"$", false, false, "", false, false);

        var string19 = Keyence.TextActions.TextAction.ReplaceText(cellJ, $@"J", false, false, "", false, false);

        foundRow = Keyence.NumericActions.NumericAction.ConvertFromObjectToInteger(string19);

        row = foundRow;

        row += -1;

        foundCount = 0;

        var string20 = "";

        foreach (var loop1 in Keyence.Activities.Samples.RepeatExtensions.RepeatCount(50))

        {

            var rowStr = Keyence.TextActions.TextAction.ConvertFromObjectToText(row);

            cellJ = Keyence.TextActions.TextAction.Concat($@"J", rowStr);

            合計ラベル = Keyence.ExcelActions.ExcelAction.GetCellValue(Keyence.ExcelActions.RangeSpecificationMethod.A1, 1, 1, cellJ, Keyence.ExcelActions.TableCellValueMode.String);

            if (Keyence.ComparisonActions.ComparisonAction.CompareString(合計ラベル, $@"合計", Keyence.ComparisonActions.StringComparingOperator.NotEqual, false))

            {

                break;

            }



            cellR = Keyence.TextActions.TextAction.Concat($@"S", rowStr);

            部署名 = Keyence.ExcelActions.ExcelAction.GetCellValue(Keyence.ExcelActions.RangeSpecificationMethod.A1, 1, 1, cellR, Keyence.ExcelActions.TableCellValueMode.String);

            cellQ = Keyence.TextActions.TextAction.Concat($@"Q", rowStr);

            取得金額＿str = Keyence.ExcelActions.ExcelAction.GetCellValue(Keyence.ExcelActions.RangeSpecificationMethod.A1, 1, 1, cellQ, Keyence.ExcelActions.TableCellValueMode.String);

            取得金額＿str = Keyence.TextActions.TextAction.ReplaceText(取得金額＿str, $@",", false, false, "", false, false);

            取得金額＿int = Keyence.NumericActions.NumericAction.ConvertFromObjectToInteger(取得金額＿str);

            if (Keyence.ComparisonActions.ComparisonAction.CompareDouble(金額＿管理, -1d, Keyence.ComparisonActions.NumberComparingOperator.Equal) && Keyence.ComparisonActions.ComparisonAction.CompareString(部署名, $@"管理", Keyence.ComparisonActions.StringComparingOperator.Equal, false))

            {

                金額＿管理 = 取得金額＿int;

                foundCount += 1;

            }



            if (Keyence.ComparisonActions.ComparisonAction.CompareDouble(金額＿営業, -1d, Keyence.ComparisonActions.NumberComparingOperator.Equal) && Keyence.ComparisonActions.ComparisonAction.CompareString(部署名, $@"営業", Keyence.ComparisonActions.StringComparingOperator.Equal, false))

            {

                金額＿営業 = 取得金額＿int;

                foundCount += 1;

            }



            if (Keyence.ComparisonActions.ComparisonAction.CompareDouble(金額＿業務, -1d, Keyence.ComparisonActions.NumberComparingOperator.Equal) && Keyence.ComparisonActions.ComparisonAction.CompareString(部署名, $@"業務", Keyence.ComparisonActions.StringComparingOperator.Equal, false))

            {

                金額＿業務 = 取得金額＿int;

                foundCount += 1;

            }



            if (Keyence.ComparisonActions.ComparisonAction.CompareDouble(金額＿営繕, -1d, Keyence.ComparisonActions.NumberComparingOperator.Equal) && Keyence.ComparisonActions.ComparisonAction.CompareString(部署名, $@"営繕", Keyence.ComparisonActions.StringComparingOperator.Equal, false))

            {

                金額＿営繕 = 取得金額＿int;

                foundCount += 1;

            }



            if (Keyence.ComparisonActions.ComparisonAction.CompareDouble(金額＿技術, -1d, Keyence.ComparisonActions.NumberComparingOperator.Equal) && Keyence.ComparisonActions.ComparisonAction.CompareString(部署名, $@"技術", Keyence.ComparisonActions.StringComparingOperator.Equal, false))

            {

                金額＿技術 = 取得金額＿int;

                foundCount += 1;

            }



            if (Keyence.ComparisonActions.ComparisonAction.CompareDouble(foundCount, 5d, Keyence.ComparisonActions.NumberComparingOperator.Equal))

            {

                break;

            }

            else

            {

                row += -1;

            }

        }



        Keyence.CommentActions.CommentScopeAction.EndComment("347a658a-cecd-4c6d-b9a1-0cfe7e6047b2");

        if (Keyence.ComparisonActions.ComparisonAction.CompareString(cfg_ENV, Env, Keyence.ComparisonActions.StringComparingOperator.NotEqual, false))

        {

        }



        Keyence.CommentActions.CommentScopeAction.EndComment("30710178-0c9e-45b6-9db5-65fa71f4223c");

        Keyence.CommentActions.CommentScopeAction.BeginComment("8ccc191a-5752-4505-87c6-8f308d1b733a", $@"楽楽精算ログイン");

        var 楽楽精算web = Keyence.WebActions.WebAction.StartEdgeWithEngineSelection($@"{RAKURAKUSEISAN_WEB}", false, true, 90, new System.Collections.Generic.List<string> { }, false, 3d);

        Keyence.WebActions.WebAction.GoToUrl(楽楽精算web, "https://rsatonality.rakurakuseisan.jp/rHqny3DOsIa/", true, 90, false);

        Keyence.WebActions.WebAction.SetWindowPosition(楽楽精算web, 0, 0, 2327, 1265);

        Keyence.WebActions.WebSingleHtmlElementAction.ClickMouseLeft(楽楽精算web, Keyence.WebActions.WebSingleHtmlElementAction.CreateSelector(Keyence.WebActions.SyntaxType.Xpath, "//div[2]/input", "#root#"), Keyence.WebActions.MouseClickActionType.Click, 0, 0, 90, false);

        var 楽楽精算ログインID = Keyence.SystemActions.SystemAction.ReadPasswordFromCredential("ログインID　楽楽精算");

        Keyence.WebActions.WebSingleHtmlElementAction.InputTextField(楽楽精算web, Keyence.WebActions.WebSingleHtmlElementAction.CreateSelector(Keyence.WebActions.SyntaxType.Xpath, "//div[2]/div/div", "#root#"), 楽楽精算ログインID, true, 0, 0, 0, true);

        Keyence.WebActions.WebSingleHtmlElementAction.ClickMouseLeft(楽楽精算web, Keyence.WebActions.WebSingleHtmlElementAction.CreateSelector(Keyence.WebActions.SyntaxType.Xpath, "//div[2]/div[2]/div", "#root#"), Keyence.WebActions.MouseClickActionType.Click, 0, 0, 90, false);

        var パスワード楽楽精算 = Keyence.SystemActions.SystemAction.ReadPasswordFromCredential("パスワード　楽楽精算");

        Keyence.WebActions.WebSingleHtmlElementAction.ClickMouseLeft(楽楽精算web, Keyence.WebActions.WebSingleHtmlElementAction.CreateSelector(Keyence.WebActions.SyntaxType.Xpath, "//input[2]", "#root#"), Keyence.WebActions.MouseClickActionType.Click, 0, 0, 90, false);

        Keyence.CommentActions.CommentScopeAction.EndComment("8ccc191a-5752-4505-87c6-8f308d1b733a");

        Keyence.CommentActions.CommentScopeAction.BeginComment("52672e1d-cc34-4b9f-8ae4-597f640df003", $@"申請作業");

        Keyence.WebActions.WebAction.GoToUrl(楽楽精算web, "https://rsatonality.rakurakuseisan.jp/rHqny3DOsIa/sapTopPage/mainView", true, 90, false);

        var 申請ファイル = Keyence.FileSystemActions.DirectoryAction.GetNewestFilePath(PDF_OUT_DIR, $@"*pdf", Keyence.FileSystemLib.FileSystemInfoFilter.CreateEmpty(), true);

        Keyence.WebActions.WebAction.SetWindowPosition(楽楽精算web, 0, 0, 2326, 1264);

        Keyence.WebActions.WebSingleHtmlElementAction.ClickMouseLeft(楽楽精算web, Keyence.WebActions.WebSingleHtmlElementAction.CreateSelector(Keyence.WebActions.SyntaxType.Xpath, "//p/a", "#root#:main"), Keyence.WebActions.MouseClickActionType.Click, 0, 0, 90, false);

        var webHandle3 = Keyence.WebActions.WebAction.WaitForWindow(楽楽精算web, true, 10d);

        Keyence.WebActions.WebAction.SetWindowPosition(楽楽精算web, 0, 0, 1637, 818);

        Keyence.WebActions.WebAction.SwitchWindow(楽楽精算web, webHandle3);

        Keyence.WebActions.WebSingleHtmlElementAction.ClickMouseLeft(楽楽精算web, Keyence.WebActions.WebSingleHtmlElementAction.CreateSelector(Keyence.WebActions.SyntaxType.Xpath, "//div/button", "#root#"), Keyence.WebActions.MouseClickActionType.Click, 0, 0, 90, false);

        var webHandle1 = Keyence.WebActions.WebAction.WaitForWindow(楽楽精算web, true, 10d);

        Keyence.WebActions.WebAction.SwitchWindow(楽楽精算web, webHandle1);

        Keyence.WebActions.WebAction.SetWindowPosition(楽楽精算web, 0, 0, 1637, 819);

        Keyence.WebActions.WebSingleHtmlElementAction.ClickMouseLeft(楽楽精算web, Keyence.WebActions.WebSingleHtmlElementAction.CreateSelector(Keyence.WebActions.SyntaxType.Xpath, "//div/button", "#root#"), Keyence.WebActions.MouseClickActionType.Click, 0, 0, 90, false);

        Keyence.WebActions.WebAction.GoToUrl(楽楽精算web, "https://rsatonality.rakurakuseisan.jp/rHqny3DOsIa/sapEbookFile/initializeView", true, 90, false);

        Keyence.WebActions.WebAction.SetWindowPosition(楽楽精算web, 0, 0, 2327, 1265);

        Keyence.WebActions.WebSingleHtmlElementAction.ClickMouseLeft(楽楽精算web, Keyence.WebActions.WebSingleHtmlElementAction.CreateSelector(Keyence.WebActions.SyntaxType.Xpath, "//input[@type='text']", "#root#"), Keyence.WebActions.MouseClickActionType.Click, 0, 0, 90, false);

        var windowHandle1 = Keyence.UIActions.WindowAction.WaitWindow("msedge.exe", "開く", true, 30d);

        Keyence.UIActions.ValueAction.SetText(Keyence.UIActions.XPathElementAction.FindFirstByProcessNameAndXPathWithTimeout("msedge.exe", "/Window[1]/ComboBox[1]/Edit[1]", false, 5d, false), $@"{申請用PDF}");

        Keyence.UIActions.MouseAction.PerformMouseAction(Keyence.UIActions.MouseEventType.Click, Keyence.UIActions.MouseButtonType.Left, Keyence.UIActions.PointAction.CreateAbsolutePointGetter(1042, 685, Keyence.UIActions.ElementSelectionAction.CreateTopLevelWindowAndSize("msedge.exe", Keyence.UIActions.ElementSelectionAction.CreateNameWildCardTopLevelSelector("開く"), 8, 0, 1200, 720, System.Windows.WindowState.Normal)), Keyence.UIActions.ModifierKeysType.None, 0d);

        Keyence.ThreadingActions.ThreadingAction.Wait(60d);

        Keyence.WebActions.WebSingleHtmlElementAction.ClickMouseLeft(楽楽精算web, Keyence.WebActions.WebSingleHtmlElementAction.CreateSelector(Keyence.WebActions.SyntaxType.Xpath, "//div[2]/div/table/tbody/tr/td/input", "#root#"), Keyence.WebActions.MouseClickActionType.Click, 0, 0, 90, false);

        Keyence.WebActions.WebSingleHtmlElementAction.InputTextField(楽楽精算web, Keyence.WebActions.WebSingleHtmlElementAction.CreateSelector(Keyence.WebActions.SyntaxType.Xpath, "//div[2]/div/table/tbody/tr/td/input", "#root#"), "2025", true, 0, 0, 0, true);

        Keyence.WebActions.WebSingleHtmlElementAction.InputTextField(楽楽精算web, Keyence.WebActions.WebSingleHtmlElementAction.CreateSelector(Keyence.WebActions.SyntaxType.Xpath, "//div[2]/div/table/tbody/tr/td/input[2]", "#root#"), "12", true, 0, 0, 0, true);

        Keyence.WebActions.WebSingleHtmlElementAction.InputTextField(楽楽精算web, Keyence.WebActions.WebSingleHtmlElementAction.CreateSelector(Keyence.WebActions.SyntaxType.Xpath, "//div[2]/div/table/tbody/tr/td/input[3]", "#root#"), "19", true, 0, 0, 0, true);

        Keyence.WebActions.WebSingleHtmlElementAction.InputTextField(楽楽精算web, Keyence.WebActions.WebSingleHtmlElementAction.CreateSelector(Keyence.WebActions.SyntaxType.Xpath, "//div[2]/div/table/tbody/tr[2]/td/input", "#root#"), "2025", true, 0, 0, 0, true);

        Keyence.WebActions.WebSingleHtmlElementAction.InputTextField(楽楽精算web, Keyence.WebActions.WebSingleHtmlElementAction.CreateSelector(Keyence.WebActions.SyntaxType.Xpath, "//div[2]/div/table/tbody/tr[2]/td/input[2]", "#root#"), "12", true, 0, 0, 0, true);

        Keyence.WebActions.WebSingleHtmlElementAction.InputTextField(楽楽精算web, Keyence.WebActions.WebSingleHtmlElementAction.CreateSelector(Keyence.WebActions.SyntaxType.Xpath, "//div[2]/div/table/tbody/tr[2]/td/input[3]", "#root#"), "9", true, 0, 0, 0, true);

        Keyence.WebActions.WebSingleHtmlElementAction.InputTextField(楽楽精算web, Keyence.WebActions.WebSingleHtmlElementAction.CreateSelector(Keyence.WebActions.SyntaxType.Xpath, "//div[2]/div/table/tbody/tr[3]/td/input[2]", "#root#"), $@"T2290005015070", true, 0, 0, 0, true);

        Keyence.WebActions.WebSingleHtmlElementAction.InputTextField(楽楽精算web, Keyence.WebActions.WebSingleHtmlElementAction.CreateSelector(Keyence.WebActions.SyntaxType.Xpath, "//div[2]/div/table/tbody/tr[4]/td/input", "#root#"), $@"日本情報サービス協同組合", true, 0, 0, 0, true);

        Keyence.WebActions.WebSingleHtmlElementAction.InputTextField(楽楽精算web, Keyence.WebActions.WebSingleHtmlElementAction.CreateSelector(Keyence.WebActions.SyntaxType.Xpath, "//td/table/tbody/tr/td/input", "#root#"), Keyence.TextActions.TextAction.ConvertFromObjectToText(金額＿管理), true, 0, 0, 0, true);

        Keyence.WebActions.WebSingleHtmlElementAction.ClickMouseLeft(楽楽精算web, Keyence.WebActions.WebSingleHtmlElementAction.CreateSelector(Keyence.WebActions.SyntaxType.Xpath, "//td/table/tbody/tr[2]/td/input", "#root#"), Keyence.WebActions.MouseClickActionType.Click, 0, 0, 90, false);

        Keyence.WebActions.WebSingleHtmlElementAction.InputTextField(楽楽精算web, Keyence.WebActions.WebSingleHtmlElementAction.CreateSelector(Keyence.WebActions.SyntaxType.Xpath, "//td/table/tbody/tr[2]/td/input", "#root#"), Keyence.TextActions.TextAction.ConvertFromObjectToText(金額＿営業), true, 0, 0, 0, true);

        Keyence.WebActions.WebSingleHtmlElementAction.ClickMouseLeft(楽楽精算web, Keyence.WebActions.WebSingleHtmlElementAction.CreateSelector(Keyence.WebActions.SyntaxType.Xpath, "//td/table/tbody/tr[3]/td/input", "#root#"), Keyence.WebActions.MouseClickActionType.Click, 0, 0, 90, false);

        Keyence.WebActions.WebSingleHtmlElementAction.InputTextField(楽楽精算web, Keyence.WebActions.WebSingleHtmlElementAction.CreateSelector(Keyence.WebActions.SyntaxType.Xpath, "//td/table/tbody/tr[3]/td/input", "#root#"), Keyence.TextActions.TextAction.ConvertFromObjectToText(金額＿業務), true, 0, 0, 0, true);

        Keyence.WebActions.WebSingleHtmlElementAction.ClickMouseLeft(楽楽精算web, Keyence.WebActions.WebSingleHtmlElementAction.CreateSelector(Keyence.WebActions.SyntaxType.Xpath, "//td/table/tbody/tr[4]/td/input", "#root#"), Keyence.WebActions.MouseClickActionType.Click, 0, 0, 90, false);

        Keyence.WebActions.WebSingleHtmlElementAction.InputTextField(楽楽精算web, Keyence.WebActions.WebSingleHtmlElementAction.CreateSelector(Keyence.WebActions.SyntaxType.Xpath, "//td/table/tbody/tr[4]/td/input", "#root#"), Keyence.TextActions.TextAction.ConvertFromObjectToText(金額＿技術), true, 0, 0, 0, true);

        Keyence.WebActions.WebSingleHtmlElementAction.ClickMouseLeft(楽楽精算web, Keyence.WebActions.WebSingleHtmlElementAction.CreateSelector(Keyence.WebActions.SyntaxType.Xpath, "//tr[5]/td/input", "#root#"), Keyence.WebActions.MouseClickActionType.Click, 0, 0, 90, false);

        Keyence.WebActions.WebSingleHtmlElementAction.InputTextField(楽楽精算web, Keyence.WebActions.WebSingleHtmlElementAction.CreateSelector(Keyence.WebActions.SyntaxType.Xpath, "//tr[5]/td/input", "#root#"), Keyence.TextActions.TextAction.ConvertFromObjectToText(金額＿営繕), true, 0, 0, 0, true);

        Keyence.ThreadingActions.ThreadingAction.Wait(5d);

        Keyence.WebActions.WebSingleHtmlElementAction.ClickMouseLeft(楽楽精算web, Keyence.WebActions.WebSingleHtmlElementAction.CreateSelector(Keyence.WebActions.SyntaxType.Xpath, "//div[4]/button", "#root#"), Keyence.WebActions.MouseClickActionType.Click, 0, 0, 90, false);

        Keyence.ThreadingActions.ThreadingAction.Wait(90d);

        Keyence.CommentActions.CommentScopeAction.EndComment("52672e1d-cc34-4b9f-8ae4-597f640df003");

        Keyence.WebActions.WebAction.EndBrowser(楽楽精算web);

        Keyence.WebActions.WebAction.EndBrowser(楽楽精算web);

        Keyence.ExcelActions.ExcelAction.CloseFile();

        Keyence.CommentActions.CommentScopeAction.BeginComment("6c47be73-041c-4d07-af89-ae40a7b16a0b", $@"完了メール送信");

        var string16 = Keyence.ExcelActions.ExcelAction.OpenFileWithSelectionModeAndReturnPath($@"C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\config\RK10_config_LOCAL.xlsx", Keyence.ExcelActions.FileOpenSelectionMode.Default, "", true, "", true, true);

        var メールアドレス1 = Keyence.ExcelActions.ExcelAction.GetCellValue(Keyence.ExcelActions.RangeSpecificationMethod.A1, 1, 1, $@"B22", Keyence.ExcelActions.TableCellValueMode.String);

        var MAIL_SUBJECT_PREFIX1 = Keyence.ExcelActions.ExcelAction.GetCellValue(Keyence.ExcelActions.RangeSpecificationMethod.A1, 1, 1, $@"B23", Keyence.ExcelActions.TableCellValueMode.String);

        var MAIL_BODY_TEMPLATE1 = Keyence.ExcelActions.ExcelAction.GetCellValue(Keyence.ExcelActions.RangeSpecificationMethod.A1, 1, 1, $@"B24", Keyence.ExcelActions.TableCellValueMode.String);

        var 申請用PDF1 = Keyence.FileSystemActions.DirectoryAction.GetNewestFilePath(PDF_OUT_DIR, $@"【申請用】日本情報サービス協同組合*.pdf", Keyence.FileSystemLib.FileSystemInfoFilter.CreateEmpty(), true);

        Keyence.OutlookActions.OutlookAction.SendHtmlMail("", メールアドレス1, "", "", MAIL_SUBJECT_PREFIX1, 申請用PDF1, false, new System.Collections.Generic.List<Keyence.HtmlMailLib.HtmlMailBodyContent> { Keyence.HtmlMailLib.HtmlBodyContentCreator.CreateString($@"「43 一般経費_日本情報サービス協同組合(ETC)明細の作成」のプロセスが完了致しました。

以下リンクからご確認願いします"), Keyence.HtmlMailLib.HtmlBodyContentCreator.CreateHyperlink($@"楽楽精算　ログイン", $@"https://rsatonality.rakurakuseisan.jp/rHqny3DOsIa/") }, "");

        Keyence.ExcelActions.ExcelAction.CloseFile();

        Keyence.CommentActions.CommentScopeAction.EndComment("6c47be73-041c-4d07-af89-ae40a7b16a0b");

    }



    static void メール送信(string メールアドレス1, string MAIL_SUBJECT_PREFIX1, string MAIL_BODY_TEMPLATE1, string 申請用PDF1)

    {

        Keyence.OutlookActions.OutlookAction.SendEmail("", メールアドレス1, "", "", MAIL_SUBJECT_PREFIX1, MAIL_BODY_TEMPLATE1, $@"{申請用PDF1}", false, "");

    }

}
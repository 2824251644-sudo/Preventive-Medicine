#!/usr/bin/env python3
"""回归测试：epidata-toolkit 全链路自动验证（防解析 bug 再现）

用法:
  python3 scripts/run_tests.py [--keep]     # --keep 保留临时产物

覆盖（每项独立子进程执行，失败即报）:
  T1 字段 JSON 预校验（validate_fields）——样本 JSON 无错误（仅警告）
  T2 qes 生成 + qes_validator（样本问卷 → qes 全绿）+ 编码检查
  T3 chk 生成自检（无空块 / 关键规则存在）
  T4 rec_check：问卷_v3.qes ↔ 问卷_v3.rec 结构一致（退出码 0）
  T5 rec_compare：空库正常比对（退出码 0）
  T6 rec_export：样本 rec → CSV / XLSX
  T7 rec_scan：含异常 rec → 检出可疑值（退出码 1）

退出码: 0=全部通过  1=有失败
"""
import os, re, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
FIX = os.path.join(SKILL, 'tests', 'fixtures')
SCRIPT = os.path.join(SKILL, 'scripts')
WORK = tempfile.mkdtemp(prefix='epidata_regression_')
PASS, FAIL = [], []


def run(name, cmd, expect=0, contains=None):
    r = subprocess.run(cmd, capture_output=True, text=True)
    out = r.stdout + r.stderr
    ok = r.returncode == expect and (contains is None or contains in out)
    (PASS if ok else FAIL).append(name)
    print(f'  {"✓" if ok else "✗"} {name}' + ('' if ok else f'  [退出码 {r.returncode}，期望 {expect}]'))
    if not ok:
        print('    └ ' + out.strip().replace('\n', '\n    └ ')[:400])
    return ok


def main():
    keep = '--keep' in sys.argv
    print('═' * 50)
    print('epidata-toolkit 回归测试')
    print(f'工作目录: {WORK}')
    print('─' * 50)

    # 样本问卷 qes/chk
    sjson = os.path.join(FIX, '样本问卷.json')
    sout = os.path.join(WORK, '样本.qes')
    run('T1 字段 JSON 预校验', [sys.executable, os.path.join(SCRIPT, 'validate_fields.py'), sjson],
        expect=2, contains='无错误')
    run('T2a qes 生成', [sys.executable, os.path.join(SCRIPT, 'qes_generator.py'), sjson, '-o', sout],
        expect=0, contains='已生成')
    run('T2b qes_validator', [sys.executable, os.path.join(SCRIPT, 'qes_validator.py'), sout],
        expect=0, contains='校验通过')
    # T2c 编码：GBK 可解码 + CRLF 行尾 + 无 BOM
    raw = open(sout, 'rb').read()
    enc_ok = not raw.startswith(b'\xef\xbb\xbf') and b'\r\n' in raw
    try:
        raw.decode('gbk')
    except UnicodeDecodeError:
        enc_ok = False
    run('T2c qes 编码 GBK+CRLF+无BOM', ['true'], expect=0 if enc_ok else 1)

    # chk 自检
    chk_path = os.path.join(WORK, '样本.chk')
    run('T3 chk 生成', [sys.executable, os.path.join(SCRIPT, 'chk_generator.py'), sjson, '-o', chk_path],
        expect=0, contains='已生成')
    if os.path.exists(chk_path):
        chk = open(chk_path, 'rb').read().decode('gbk', errors='replace')
        # 空块 = 字段名行后直接 END（无任何规则行）；LABELBLOCK 尾部的"  END/END"缩进结构不算
        empty_blocks = len(re.findall(r'(?m)^[A-Za-z][A-Za-z0-9]*\r\nEND\r\n', chk))
        jumps_ok = all(t in chk for t in ('OCCUPO', 'MUSTENTER', 'RANGE'))
        run('T3a chk 无空块', ['true'], expect=0 if empty_blocks == 0 else 1)
        run('T3b chk 关键规则存在', ['true'], expect=0 if jumps_ok else 1)

    # rec_check（真实 v3）
    run('T4 rec↔qes 结构校验（v3 真实）',
        [sys.executable, os.path.join(SCRIPT, 'rec_check.py'),
         os.path.join(FIX, '问卷_v3.qes'), os.path.join(FIX, '问卷_v3.rec')],
        expect=0, contains='完全一致')

    # rec_compare（空库）
    run('T5 rec_compare 空库正常', [sys.executable, os.path.join(SCRIPT, 'rec_compare.py'),
        os.path.join(FIX, '肺结核.rec'), os.path.join(FIX, '肺结核.rec')],
        expect=0, contains='无录入记录')

    # rec_export
    run('T6 rec 导出 CSV', [sys.executable, os.path.join(SCRIPT, 'rec_export.py'),
        os.path.join(FIX, '问卷_v3.rec'), '-o', os.path.join(WORK, '导出'), '--qes', os.path.join(FIX, '问卷_v3.qes')],
        expect=0, contains='389')
    run('T6b rec 导出 XLSX', [sys.executable, os.path.join(SCRIPT, 'rec_export.py'),
        os.path.join(FIX, '问卷_v3.rec'), '-o', os.path.join(WORK, '导出x'), '-f', 'xlsx'],
        expect=0, contains='Excel')

    # rec_scan（构造异常：AGE=200 >120）
    scan = os.path.join(WORK, '扫描.rec')
    subprocess.run([sys.executable, '-c', f'''
lines = ['_LABEL1        1   1  30   0   0   0   0 112 扫描测试',
          '#AGE          1   2  30   1   3   0   3 112 AGE年龄：',
          '#SEX          1   3  30   6   1   0   1 112 SEX性别：']
open(r"{scan}", "wb").write((f"3 2 Filelabel: 1\\r\\n" + "\\r\\n".join(lines)).encode("gbk") + b"\\r\\n" + b"200" + b"3" + b"035" + b"1")
'''], check=True)
    run('T7 rec_scan 异常检出', [sys.executable, os.path.join(SCRIPT, 'rec_scan.py'), scan],
        expect=1, contains='年龄 200')

    # 清理
    if not keep:
        shutil.rmtree(WORK, ignore_errors=True)

    print('─' * 50)
    if FAIL:
        print(f'✗ 失败 {len(FAIL)} 项: {FAIL}')
        sys.exit(1)
    print(f'✓ 全部通过（{len(PASS)} 项）')
    sys.exit(0)


if __name__ == '__main__':
    main()

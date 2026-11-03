#!/usr/bin/env node
/**
 * 生成 DevEco/hvigor 兼容的签名材料（material 目录 + 加密后的密码 hex）。
 *
 * 背景：hvigor 6.x 的签名任务不接受明文密码 —— build-profile.json5 里的
 * storePassword/keyPassword 必须是 AES-128-GCM 密文（hex），且 p12 同目录下要有
 * material/ 目录（fd/ac/ce），hvigor 用 material 派生密钥解密密码。
 * 本脚本按 hvigor 的 DecipherUtil 格式生成：
 *   rootKey = PBKDF2(xorHex(fd×3, component).toString(), salt, 10000, 16, sha256)
 *   ce 文件 = AES-128-GCM(rootKey, aesKey)
 *   密码 hex = [4B 明文长度][IV 12B][密文][GCM tag 16B]，用 aesKey 加密
 *
 * 用法：
 *   node scripts/gen-signing-material.js \
 *     --signing-dir <p12 所在目录> \
 *     --store-password <p12 密码> \
 *     --key-password <key 密码> \
 *     [--force]
 *
 * 输出：<signing-dir>/material/{fd/0..2, ac, ce}，并把两个 hex 密码写入
 *      <signing-dir>/signing-passwords.json（不要提交到仓库！）。
 *
 * 之后运行 scripts/inject-signing.sh 把 hex 密码与证书路径注入 build-profile.json5。
 * ⚠️ 该 material 目录与密码绑定；重新生成会让旧的 build-profile 密码失效。
 */
'use strict'

const fs = require('fs')
const path = require('path')
const crypto = require('crypto')

// hvigor DecipherUtil.component（硬编码常量，勿改）
const COMPONENT = Buffer.from([49, 243, 9, 115, 214, 175, 91, 184, 211, 190, 177, 88, 101, 131, 192, 119])
const IV_LEN = 12
const TAG_LEN = 16
const KEY_LEN = 16

function fail(msg) {
  console.error(`[gen-signing-material] ${msg}`)
  process.exit(1)
}

function parseArgs(argv) {
  const out = { force: false }
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i]
    if (a === '--force') {
      out.force = true
    } else if (a === '--signing-dir') {
      out.signingDir = argv[++i]
    } else if (a === '--store-password') {
      out.storePassword = argv[++i]
    } else if (a === '--key-password') {
      out.keyPassword = argv[++i]
    }
  }
  return out
}

/** hvigor 的 4 段异或：fd0 ^ fd1 ^ fd2 ^ component（每段 16 字节）。 */
function xorComponents(parts) {
  const out = Buffer.from(parts[0])
  for (let i = 1; i < parts.length; i++) {
    if (parts[i].length !== KEY_LEN) {
      fail(`签名材料长度错误：期望 ${KEY_LEN} 字节，得到 ${parts[i].length}`)
    }
    for (let j = 0; j < KEY_LEN; j++) {
      out[j] = out[j] ^ parts[i][j]
    }
  }
  return out
}

/** 与 DecipherUtil.encrypt 对应的 AES-128-GCM 打包格式。 */
function encryptBlob(key, plain) {
  const iv = crypto.randomBytes(IV_LEN)
  const cipher = crypto.createCipheriv('aes-128-gcm', key, iv)
  const ciphertext = Buffer.concat([cipher.update(plain), cipher.final()])
  const tag = cipher.getAuthTag()
  // hvigor DecipherUtil.decrypt 解析：head = 明文长度 + 16（GCM tag 长度）
  const head = Buffer.alloc(4)
  head.writeUInt32BE(ciphertext.length + TAG_LEN, 0)
  return Buffer.concat([head, iv, ciphertext, tag])
}

function writeSingleFileDir(dir, name) {
  fs.mkdirSync(dir, { recursive: true })
  // readDirBytes 要求目录内恰好一个文件；用随机 16 字节内容
  fs.writeFileSync(path.join(dir, name), crypto.randomBytes(KEY_LEN))
}

function main() {
  const args = parseArgs(process.argv.slice(2))
  if (!args.signingDir || !args.storePassword || !args.keyPassword) {
    fail('缺少参数：--signing-dir/--store-password/--key-password 均为必填')
  }
  const signingDir = path.resolve(args.signingDir)
  if (!fs.existsSync(signingDir)) {
    fail(`signing-dir 不存在：${signingDir}`)
  }
  const materialDir = path.join(signingDir, 'material')
  if (fs.existsSync(materialDir) && !args.force) {
    fail(`material 目录已存在：${materialDir}（确要覆盖请加 --force；旧密码会失效）`)
  }
  if (args.storePassword.length === 0 || args.keyPassword.length === 0) {
    fail('密码不能为空')
  }
  fs.rmSync(materialDir, { recursive: true, force: true })

  // fd: 3 个子目录，每个恰好 1 个文件（各 16 字节）
  fs.mkdirSync(path.join(materialDir, 'fd'), { recursive: true })
  for (let i = 0; i < 3; i++) {
    writeSingleFileDir(path.join(materialDir, 'fd', String(i)), `fd-${i}.bin`)
  }
  const fd0 = fs.readFileSync(path.join(materialDir, 'fd', '0', 'fd-0.bin'))
  const fd1 = fs.readFileSync(path.join(materialDir, 'fd', '1', 'fd-1.bin'))
  const fd2 = fs.readFileSync(path.join(materialDir, 'fd', '2', 'fd-2.bin'))
  // ac: 1 个 salt 文件（16 字节随机）
  writeSingleFileDir(path.join(materialDir, 'ac'), 'salt.bin')
  const salt = fs.readFileSync(path.join(materialDir, 'ac', 'salt.bin'))

  // rootKey：注意 hvigor 使用 Buffer/Int8Array.toString()（UTF-8 字符串）作为 PBKDF2 密码
  const xor = xorComponents([fd0, fd1, fd2, COMPONENT])
  const rootKey = crypto.pbkdf2Sync(xor.toString(), salt, 10000, KEY_LEN, 'sha256')

  // ce: 工作密钥（AES key）用 rootKey 加密
  const aesKey = crypto.randomBytes(KEY_LEN)
  const workBlob = encryptBlob(rootKey, aesKey)
  writeSingleFileDir(path.join(materialDir, 'ce'), 'work.bin')
  const ceDir = path.join(materialDir, 'ce')
  fs.writeFileSync(path.join(ceDir, fs.readdirSync(ceDir)[0]), workBlob)

  // 密码密文（hex，大写；hvigor 用同一个 aesKey 解密）
  const storePwdHex = encryptBlob(aesKey, Buffer.from(args.storePassword, 'utf8')).toString('hex').toUpperCase()
  const keyPwdHex = encryptBlob(aesKey, Buffer.from(args.keyPassword, 'utf8')).toString('hex').toUpperCase()

  const out = {
    materialDir: materialDir,
    storePassword: storePwdHex,
    keyPassword: keyPwdHex,
  }
  const outFile = path.join(signingDir, 'signing-passwords.json')
  fs.writeFileSync(outFile, JSON.stringify(out, null, 2) + '\n')
  console.log(`[gen-signing-material] OK`)
  console.log(`  material: ${materialDir}`)
  console.log(`  passwords: ${outFile}（勿提交到 git）`)
}

main()

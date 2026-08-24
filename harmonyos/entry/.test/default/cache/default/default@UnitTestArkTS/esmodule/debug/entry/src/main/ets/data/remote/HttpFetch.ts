import http from "@ohos:net.http";
class BjcCov {
    coverage: {
        [key: string]: string | number;
    };
    constructor(covData: object) {
        const gcv = "__coverage__";
        let coverage = globalThis[gcv] || (globalThis[gcv] = {});
        if (!coverage[covData.path] && true) {
            coverage[covData.path] = covData;
        }
        this.coverage = coverage[covData.path];
    }
    instrumentFunction(func: number) {
        this.coverage.functions[func].count++;
        this.coverage.functions[func].regions[0].count++;
    }
    instrumentRegion(func: number, region: number) {
        this.coverage.functions[func].regions[region].count++;
    }
    instrumentReturn(func: number, retIdx: number) {
        this.coverage.functions[func].returnes[retIdx].count++;
    }
    instrumentBranch(func: number, branch: number, trueOrFalse: boolean) {
        if (trueOrFalse) {
            this.coverage.functions[func].branches[branch].trueCount++;
            for (let r of Object.values(this.coverage.functions[func].branches[branch].group)) {
                if (r !== branch) {
                    this.coverage.functions[func].branches[r as number].falseCount++;
                }
            }
        }
        else {
            this.coverage.functions[func].branches[branch].falseCount++;
        }
    }
}
let bjccovmt7djy59 = new BjcCov({ version: "bjc v1.0.0", versionCode: 10000, path: "entry/src/main/ets/data/remote/HttpFetch.ets", hash: "a8e4461d4bb72b168025a255dd6bd5bbf903063eba90bfeb5d0a537b6f4093c6", lineCnt: 80, count: 0, projectPath: "", functions: { 0: { name: "HttpError.constructor", count: 0, regions: { 0: { startLoc: { line: 9, col: 3 }, endLoc: { line: 12, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 10, col: 5 }, endLoc: { line: 12, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 0 }, 1: { name: "HttpFetch.fetch", count: 0, regions: { 0: { startLoc: { line: 32, col: 3 }, endLoc: { line: 73, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 34, col: 5 }, endLoc: { line: 71, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 36, col: 11 }, endLoc: { line: 60, col: 8 }, count: 0, ignored: 0 }, 3: { startLoc: { line: 60, col: 9 }, endLoc: { line: 68, col: 8 }, count: 0, ignored: 0 }, 4: { startLoc: { line: 68, col: 17 }, endLoc: { line: 70, col: 8 }, count: 0, ignored: 0 }, 5: { startLoc: { line: 47, col: 46 }, endLoc: { line: 49, col: 10 }, count: 0, ignored: 0 }, 6: { startLoc: { line: 50, col: 47 }, endLoc: { line: 52, col: 10 }, count: 0, ignored: 0 }, 7: { startLoc: { line: 53, col: 29 }, endLoc: { line: 55, col: 10 }, count: 0, ignored: 0 }, 8: { startLoc: { line: 56, col: 43 }, endLoc: { line: 58, col: 10 }, count: 0, ignored: 0 }, 9: { startLoc: { line: 61, col: 37 }, endLoc: { line: 63, col: 10 }, count: 0, ignored: 0 }, 10: { startLoc: { line: 65, col: 36 }, endLoc: { line: 67, col: 10 }, count: 0, ignored: 0 }, 11: { startLoc: { line: 72, col: 5 }, endLoc: { line: 73, col: 4 }, count: 0, ignored: 0 }, 12: { startLoc: { line: 59, col: 9 }, endLoc: { line: 60, col: 8 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 47, col: 13 }, endLoc: { line: 47, col: 44 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 1: { startLoc: { line: 50, col: 13 }, endLoc: { line: 50, col: 45 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 2: { startLoc: { line: 53, col: 13 }, endLoc: { line: 53, col: 27 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 3: { startLoc: { line: 56, col: 13 }, endLoc: { line: 56, col: 41 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 4: { startLoc: { line: 61, col: 13 }, endLoc: { line: 61, col: 35 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 5: { startLoc: { line: 65, col: 13 }, endLoc: { line: 65, col: 34 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 1 }, 2: { name: "HttpFetch.sleep", count: 0, regions: { 0: { startLoc: { line: 75, col: 3 }, endLoc: { line: 79, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 76, col: 5 }, endLoc: { line: 79, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 2 }, 3: { name: "anonymous_0", count: 0, regions: { 0: { startLoc: { line: 76, col: 29 }, endLoc: { line: 78, col: 6 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 77, col: 7 }, endLoc: { line: 78, col: 6 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 3 }, 4: { name: "anonymous_1", count: 0, regions: { 0: { startLoc: { line: 77, col: 18 }, endLoc: { line: 77, col: 37 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 77, col: 26 }, endLoc: { line: 77, col: 37 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 4 } }, exeLine: { 0: 5, 1: 7, 2: 8, 3: 9, 4: 10, 5: 11, 6: 16, 7: 19, 8: 20, 9: 21, 10: 22, 11: 23, 12: 24, 13: 25, 14: 32, 15: 33, 16: 34, 17: 35, 18: 36, 19: 37, 20: 38, 21: 39, 22: 40, 23: 41, 24: 42, 25: 43, 26: 45, 27: 46, 28: 47, 29: 48, 30: 50, 31: 51, 32: 53, 33: 54, 34: 56, 35: 57, 36: 59, 37: 60, 38: 61, 39: 62, 40: 64, 41: 65, 42: 66, 43: 68, 44: 69, 45: 72, 46: 75, 47: 76, 48: 77 } });
export class HttpError extends Error {
    code: number;
    constructor(message: string, code: number = 0) {
        bjccovmt7djy59.instrumentFunction(0);
        bjccovmt7djy59.instrumentRegion(0, 1);
        super(message);
        this.code = code;
    }
}
/** 认证失败 (401/403) —— token 失效或过期。 */
export class AuthHttpError extends HttpError {
}
export class HttpFetch {
    static readonly USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Gecko/20100101 Firefox/148.0';
    static readonly MAX_BODY_BYTES = 4 * 1024 * 1024;
    static readonly CONNECT_TIMEOUT_MS = 10000;
    static readonly READ_TIMEOUT_MS = 15000;
    static readonly RETRY_BACKOFF_MS: number[] = [500, 1500, 3000];
    /**
     * GET 请求, 自动重试, 返回响应体文本 (截断到 MAX_BODY_BYTES)。
     * 401/403 -> AuthHttpError; 404 -> HttpError("工作区不存在 (HTTP 404)");
     * 其他非 2xx -> HttpError("请求返回 HTTP <code>"); 网络错误重试耗尽后抛出。
     */
    static async fetch(url: string, headers: Record<string, string>, retries: number = 2): Promise<string> {
        bjccovmt7djy59.instrumentFunction(1);
        let lastErr: Error | null = null;
        for (let attempt = 0; attempt < retries; attempt++) {
            bjccovmt7djy59.instrumentRegion(1, 1);
            const req = http.createHttp();
            try {
                bjccovmt7djy59.instrumentRegion(1, 2);
                const resp = await req.request(url, {
                    method: http.RequestMethod.GET,
                    header: headers,
                    expectDataType: http.HttpDataType.STRING,
                    connectTimeout: HttpFetch.CONNECT_TIMEOUT_MS,
                    readTimeout: HttpFetch.READ_TIMEOUT_MS,
                    usingCache: false,
                });
                const status: number = resp.responseCode as number;
                let body = '';
                if (typeof resp.result === 'string') {
                    bjccovmt7djy59.instrumentBranch(1, 0, true);
                    bjccovmt7djy59.instrumentRegion(1, 5);
                    body = resp.result.substring(0, HttpFetch.MAX_BODY_BYTES);
                }
                else {
                    bjccovmt7djy59.instrumentBranch(1, 0, false);
                }
                if (status === 401 || status === 403) {
                    bjccovmt7djy59.instrumentBranch(1, 1, true);
                    bjccovmt7djy59.instrumentRegion(1, 6);
                    throw new AuthHttpError(`认证失败 (HTTP ${status})，请重新登录`, status);
                }
                else {
                    bjccovmt7djy59.instrumentBranch(1, 1, false);
                }
                if (status === 404) {
                    bjccovmt7djy59.instrumentBranch(1, 2, true);
                    bjccovmt7djy59.instrumentRegion(1, 7);
                    throw new HttpError('工作区不存在 (HTTP 404)', 404);
                }
                else {
                    bjccovmt7djy59.instrumentBranch(1, 2, false);
                }
                if (status < 200 || status > 299) {
                    bjccovmt7djy59.instrumentBranch(1, 3, true);
                    bjccovmt7djy59.instrumentRegion(1, 8);
                    throw new HttpError(`请求返回 HTTP ${status}`, status);
                }
                else {
                    bjccovmt7djy59.instrumentBranch(1, 3, false);
                }
                bjccovmt7djy59.instrumentRegion(1, 12);
                return body;
            }
            catch (e) {
                bjccovmt7djy59.instrumentRegion(1, 3);
                if (e instanceof HttpError) {
                    bjccovmt7djy59.instrumentBranch(1, 4, true);
                    bjccovmt7djy59.instrumentRegion(1, 9);
                    throw e; // 业务错误不重试
                }
                else {
                    bjccovmt7djy59.instrumentBranch(1, 4, false);
                }
                lastErr = (e as Error);
                if (attempt < retries - 1) {
                    bjccovmt7djy59.instrumentBranch(1, 5, true);
                    bjccovmt7djy59.instrumentRegion(1, 10);
                    await HttpFetch.sleep(HttpFetch.RETRY_BACKOFF_MS[Math.min(attempt, HttpFetch.RETRY_BACKOFF_MS.length - 1)]);
                }
                else {
                    bjccovmt7djy59.instrumentBranch(1, 5, false);
                }
            }
            finally {
                bjccovmt7djy59.instrumentRegion(1, 4);
                req.destroy();
            }
        }
        bjccovmt7djy59.instrumentRegion(1, 11);
        throw new HttpError(`网络错误: ${lastErr?.message ?? '未知'}`, 0);
    }
    static async sleep(ms: number): Promise<void> {
        bjccovmt7djy59.instrumentFunction(2);
        bjccovmt7djy59.instrumentRegion(2, 1);
        await new Promise<void>((resolve) => {
            bjccovmt7djy59.instrumentFunction(3);
            bjccovmt7djy59.instrumentRegion(3, 1);
            setTimeout(() => { bjccovmt7djy59.instrumentFunction(4); bjccovmt7djy59.instrumentRegion(4, 1); resolve(); }, ms);
        });
    }
}

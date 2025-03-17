import asyncio
from loguru import logger
import random
import primp
from src.model.help.captcha import Capsolver, Solvium
from src.utils.config import Config
from eth_account import Account
import hashlib
from pynocaptcha import CloudFlareCracker, TlsV1Cracker
from curl_cffi.requests import AsyncSession
from src.model.monad_xyz.tls_op import make_wanda_request
from src.utils.tls_client import TLSClient
import json
import platform


async def faucet(
    session: primp.AsyncClient,
    account_index: int,
    config: Config,
    wallet: Account,
    proxy: str,
) -> bool:
    for retry in range(config.SETTINGS.ATTEMPTS):
        try:
            logger.info(
                f"[{account_index}] | Starting faucet for account {wallet.address}..."
            )
            user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
            href = "https://testnet.monad.xyz/"

            # # First get the Vercel challenge token
            # response = await session.post(
            #     "http://api.nocaptcha.io/api/wanda/vercel/universal",
            #     headers={
            #         "User-Token": config.FAUCET.NOCAPTCHA_API_KEY,
            #         "Developer-Id": "SWVtru",
            #     },
            #     json={
            #         "href": href,
            #         "user_agent": user_agent,
            #         "proxy": proxy,
            #         "timeout": 30,
            #     },
            # )

            # vercel_resp = response.json()

            # if vercel_resp.get("status") != 1:
            #     raise Exception(
            #         f"Failed to solve Vercel challenge: {vercel_resp.get('msg')}"
            #     )

            # extra = vercel_resp["extra"]

            # # Prepare headers with Vercel token - exactly matching working example
            # headers = {
            #     "sec-ch-ua": extra["sec-ch-ua"],
            #     "sec-ch-ua-mobile": "?0",
            #     "sec-ch-ua-platform": extra["sec-ch-ua-platform"],
            #     "upgrade-insecure-requests": "1",
            #     "user-agent": extra["user-agent"],
            #     "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            #     "sec-fetch-site": "same-origin",
            #     "sec-fetch-mode": "navigate",
            #     "sec-fetch-dest": "document",
            #     "referer": href,
            #     "accept-encoding": "gzip, deflate, br, zstd",
            #     "accept-language": extra["accept-language"],
            #     "cookie": "_vcrcs=" + vercel_resp["data"]["_vcrcs"],
            #     "priority": "u=0, i",
            # }

            if config.FAUCET.USE_SOLVIUM_FOR_CLOUDFLARE:
                logger.info(
                    f"[{account_index}] | Solving Cloudflare challenge with Solvium..."
                )
                solvium = Solvium(
                    api_key=config.FAUCET.SOLVIUM_API_KEY,
                    session=session,
                    proxy=proxy,
                )

                result = await solvium.solve_captcha(
                    sitekey="0x4AAAAAAA-3X4Nd7hf3mNGx",
                    pageurl="https://testnet.monad.xyz/",
                )
                cf_result = result

            elif config.FAUCET.USE_CAPSOLVER_FOR_CLOUDFLARE:
                logger.info(
                    f"[{account_index}] | Solving Cloudflare challenge with Capsolver..."
                )
                capsolver = Capsolver(
                    api_key=config.FAUCET.CAPSOLVER_API_KEY,
                    proxy=proxy,
                    session=session,
                )
                cf_result = await capsolver.solve_turnstile(
                    "0x4AAAAAAA-3X4Nd7hf3mNGx",
                    "https://testnet.monad.xyz/",
                )

            else:
                # Solve Cloudflare challenge - matching working example configuration
                logger.info(
                    f"[{account_index}] | Solving Cloudflare challenge with Nocaptcha..."
                )
                cracker = CloudFlareCracker(
                    internal_host=True,
                    user_token=config.FAUCET.NOCAPTCHA_API_KEY,
                    href=href,
                    sitekey="0x4AAAAAAA-3X4Nd7hf3mNGx",
                    proxy=proxy,
                    debug=False,
                    show_ad=False,
                    timeout=60,
                )
                cf_result = cracker.crack()
                cf_result = cf_result["token"]

            if not cf_result:
                raise Exception("Failed to solve Cloudflare challenge")

            logger.success(f"[{account_index}] | Cloudflare challenge solved")

            # Generate visitor ID the same way as working example
            visitor_id = hashlib.md5(str(random.random()).encode()).hexdigest()

            json_data = {
                "address": wallet.address,
                "visitorId": visitor_id,
                "cloudFlareResponseToken": cf_result,
            }

            # Заменяем TlsV1Cracker на асинхронный запрос
            logger.info(f"[{account_index}] | Sending claim request...")

            headers = {
                "sec-ch-ua-platform": '"Windows"',
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
                "sec-ch-ua": '"Not(A:Brand";v="99", "Google Chrome";v="133", "Chromium";v="133"',
                "content-type": "application/json",
                "sec-ch-ua-mobile": "?0",
                "accept": "*/*",
                "origin": "https://testnet.monad.xyz",
                "sec-fetch-site": "same-origin",
                "sec-fetch-mode": "cors",
                "sec-fetch-dest": "empty",
                "referer": "https://testnet.monad.xyz/",
                "accept-language": "en-GB,en;q=0.9",
                "priority": "u=1, i",
            }

            # wanda_result = await make_wanda_request(
            #     session=session,
            #     user_token=config.FAUCET.NOCAPTCHA_API_KEY,
            #     url=f"{href}api/claim",
            #     method="post",
            #     headers=headers,
            #     json_data=json_data,
            #     proxy=proxy,
            #     http2=True,
            #     timeout=30,
            #     debug=False,
            # )

            # if wanda_result and wanda_result["data"]:
            #     claim_result = wanda_result["data"]
            # else:
            #     raise Exception(f"wrong wanda_result: {wanda_result}")

            # response_text = claim_result.get("response", {}).get("text", "")

            # Проверка операционной системы
            if platform.system().lower() != "windows":
                curl_session = AsyncSession(
                    impersonate="chrome131",
                    proxies={"http": f"http://{proxy}", "https": f"http://{proxy}"},
                    verify=False,
                )

                claim_result = await curl_session.post(
                    "https://faucet-claim.monadinfra.com/",
                    headers=headers,
                    json=json_data,
                )
                response_text = claim_result.text
                status_code = claim_result.status_code

            else:
                logger.info(f"[{account_index}] | Initializing TLS client...")
                tls_client = TLSClient()
                # response_text = claim_result.text

                # Выполняем запрос через TLS клиент
                logger.info(
                    f"[{account_index}] | Sending claim request via TLS client..."
                )

                # Преобразуем прокси в формат http://user:pass@ip:port
                proxy_parts = proxy.split("@")
                if len(proxy_parts) == 2:
                    proxy_url = f"http://{proxy}"
                else:
                    proxy_url = f"http://{proxy}"

                response = tls_client.make_request(
                    url="https://faucet-claim.monadinfra.com/",
                    method="POST",
                    headers=headers,
                    data=json_data,
                    proxy=proxy_url,
                    tls_client_identifier="chrome_133",
                    follow_redirects=False,
                    timeout_seconds=30,
                )

                # Получаем текст ответа
                response_text = response.get("body", "")
                status_code = response.get("status", 0)

            logger.info(
                f"[{account_index}] | Received response with status code: {status_code}"
            )

            if "Faucet is currently closed" in response_text:
                logger.error(f"[{account_index}] | Faucet is currently closed")
                return False

            if "used Cloudflare to restrict access" in response_text:
                logger.error(f"[{account_index}] | Cloudflare solved wrong...")
                continue

            if not response_text:
                raise Exception("Failed to send claim request")

            if '"Success"' in response_text:
                logger.success(
                    f"[{account_index}] | Successfully got tokens from faucet"
                )
                return True

            if "Claimed already" in response_text:
                logger.success(
                    f"[{account_index}] | Already claimed tokens from faucet"
                )
                return True

            if '"message":"Success"' in response_text:
                logger.success(
                    f"[{account_index}] | Successfully got tokens from faucet"
                )
                return True
            else:
                if "FUNCTION_INVOCATION_TIMEOUT" in response_text:
                    logger.error(
                        f"[{account_index}] | Failed to get tokens from faucet: server is not responding, wait..."
                    )
                elif "Vercel Security Checkpoint" in response_text:
                    logger.error(
                        f"[{account_index}] | Failed to solve Vercel challenge, trying again..."
                    )
                    continue
                elif "Server error on QuickNode API" in response_text:
                    logger.error(
                        f"[{account_index}] | FAUCET DOES NOT WORK, QUICKNODE IS DOWN"
                    )
                elif "Over Enterprise free quota" in response_text:
                    logger.error(
                        f"[{account_index}] | MONAD IS SHIT, FAUCET DOES NOT WORK, TRY LATER"
                    )
                    return False
                elif "invalid-keys" in response_text:
                    logger.error(
                        f"[{account_index}] | PLEASE UPDATE THE BOT USING GITHUB"
                    )
                    return False
                else:
                    logger.error(
                        f"[{account_index}] | Failed to get tokens from faucet: {response_text}"
                    )
                await asyncio.sleep(3)

        except Exception as e:
            random_pause = random.randint(
                config.SETTINGS.RANDOM_PAUSE_BETWEEN_ACTIONS[0],
                config.SETTINGS.RANDOM_PAUSE_BETWEEN_ACTIONS[1],
            )
            if "operation timed out" in str(e):
                logger.error(
                    f"[{account_index}] | Error faucet to monad.xyz ({retry + 1}/{config.SETTINGS.ATTEMPTS}): Connection timed out. Next faucet in {random_pause} seconds"
                )
            else:
                logger.error(
                    f"[{account_index}] | Error faucet to monad.xyz ({retry + 1}/{config.SETTINGS.ATTEMPTS}): {e}. Next faucet in {random_pause} seconds"
                )
            await asyncio.sleep(random_pause)
            continue
    return False

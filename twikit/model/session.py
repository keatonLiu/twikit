from typing import Optional, Union

from noble_tls import Session, Client


class BaseSession(Session):
    def __init__(self, *args, **kwargs):
        kwargs['client'] = Client.CHROME_133
        kwargs['random_tls_extension_order'] = True
        super().__init__(*args, **kwargs)

    async def request(
            self,
            method: str,
            url: str,
            params: Optional[dict] = None,  # Optional[dict[str, str]]
            data: Optional[Union[str, dict]] = None,
            headers: Optional[dict] = None,  # Optional[dict[str, str]]
            cookies: Optional[dict] = None,  # Optional[dict[str, str]]
            json: Optional[dict] = None,  # Optional[dict]
            allow_redirects: Optional[bool] = True,
            insecure_skip_verify: Optional[bool] = False,
            timeout_seconds: Optional[int] = None,
            timeout: Optional[int] = None,
            proxy: Optional[dict] = None,  # Optional[dict[str, str]]
            is_byte_response: Optional[bool] = False
    ):
        return await self.execute_request(
            method=method,
            url=url,
            params=params,
            data=data,
            headers=headers,
            cookies=cookies,
            json=json,
            allow_redirects=allow_redirects,
            insecure_skip_verify=insecure_skip_verify,
            timeout_seconds=timeout_seconds,
            timeout=timeout,
            proxy=proxy,
            is_byte_response=is_byte_response
        )

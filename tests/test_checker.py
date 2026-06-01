import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import aiodns

from checker import dns_filter, whois_verify, check_batch


@pytest.mark.asyncio
async def test_dns_filter_nxdomain_included():
    with patch('checker.aiodns.DNSResolver') as MockResolver:
        mock_resolver = MagicMock()
        MockResolver.return_value = mock_resolver
        err = aiodns.error.DNSError(aiodns.error.ARES_ENOTFOUND, 'NXDOMAIN')
        mock_resolver.query = AsyncMock(side_effect=err)
        result = await dns_filter(['freetest99z.com'], concurrency=1)
        assert 'freetest99z.com' in result


@pytest.mark.asyncio
async def test_dns_filter_resolved_excluded():
    with patch('checker.aiodns.DNSResolver') as MockResolver:
        mock_resolver = MagicMock()
        MockResolver.return_value = mock_resolver
        mock_resolver.query = AsyncMock(return_value=MagicMock())
        result = await dns_filter(['google.com'], concurrency=1)
        assert 'google.com' not in result


def test_whois_verify_registered_returns_false():
    with patch('checker.whois.whois') as mock_whois:
        w = MagicMock()
        w.domain_name = 'GOOGLE.COM'
        mock_whois.return_value = w
        assert whois_verify('google.com') is False


def test_whois_verify_available_returns_true():
    with patch('checker.whois.whois') as mock_whois:
        w = MagicMock()
        w.domain_name = None
        mock_whois.return_value = w
        assert whois_verify('freetest99z.com') is True


def test_whois_verify_exception_returns_false():
    with patch('checker.whois.whois', side_effect=Exception('timeout')):
        assert whois_verify('freetest99z.com', retries=1, delay=0) is False


def test_check_batch_returns_available():
    with patch('checker.asyncio.run', return_value=['freetest99z.com']), \
         patch('checker.whois_verify', return_value=True), \
         patch('checker.time.sleep'):
        result = check_batch(['google.com', 'freetest99z.com'])
        assert result == ['freetest99z.com']

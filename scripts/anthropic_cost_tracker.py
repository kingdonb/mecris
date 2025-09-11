import os
import time
import requests
import json
import argparse
from functools import lru_cache
from datetime import datetime, timedelta, UTC

class AnthropicCostTracker:
    def __init__(self, admin_api_key=None):
        """
        Initialize the Anthropic Cost Tracker
        
        :param admin_api_key: Optional Admin API key. If not provided, uses ANTHROPIC_ADMIN_KEY env var
        """
        self.admin_api_key = admin_api_key or os.environ.get('ANTHROPIC_ADMIN_KEY')
        if not self.admin_api_key:
            raise ValueError("No Anthropic Admin API key provided. This requires organization access.")
        
        # Rate limiting parameters
        self._last_api_call = 0
        self._min_interval = 10  # seconds between API calls
        
        # Caching 
        self.usage_cache = {}
        self.cost_cache = {}
    
    def _rate_limited_request(self, url, method='GET', **kwargs):
        """
        Make a rate-limited API request
        
        :param url: API endpoint URL
        :param method: HTTP method
        :param kwargs: Additional request parameters
        :return: API response
        """
        current_time = time.time()
        
        # Enforce rate limiting
        if current_time - self._last_api_call < self._min_interval:
            wait_time = self._min_interval - (current_time - self._last_api_call)
            time.sleep(wait_time)
        
        # Prepare headers for Admin API
        headers = {
            'x-api-key': self.admin_api_key,
            'anthropic-version': '2023-06-01',
            'Content-Type': 'application/json'
        }
        kwargs['headers'] = {**kwargs.get('headers', {}), **headers}
        
        # Make the request
        if method == 'GET':
            response = requests.get(url, **kwargs)
        elif method == 'POST':
            response = requests.post(url, **kwargs)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")
        
        # Update last API call time
        self._last_api_call = time.time()
        
        # Raise for HTTP errors
        response.raise_for_status()
        
        return response.json()
    
    def get_usage(self, start_time=None, end_time=None, bucket_width='1d'):
        """
        Fetch API usage data with caching
        
        :param start_time: Optional start time for usage data
        :param end_time: Optional end time for usage data
        :param bucket_width: Bucket width ('1h' for hourly, '1d' for daily)
        :return: Usage data dictionary
        """
        # Use current time if not specified, ensure proper date range
        if end_time is None:
            end_time = datetime.now(UTC)
        if start_time is None:
            start_time = end_time - timedelta(days=1)
        
        # Convert to clean ISO format strings with Z suffix (API expects this format)
        start_str = start_time.replace(microsecond=0).isoformat().replace('+00:00', 'Z')
        
        # For hourly buckets on current day, don't specify end time to avoid future dates
        if bucket_width == '1h' and start_time.date() >= datetime.now(UTC).date():
            params = {
                'starting_at': start_str,
                'bucket_width': bucket_width
            }
        else:
            end_str = end_time.replace(microsecond=0).isoformat().replace('+00:00', 'Z')
            params = {
                'starting_at': start_str,
                'ending_at': end_str,
                'bucket_width': bucket_width
            }
        
        # Check cache first
        cache_key = (start_str, params.get('ending_at', 'open'), bucket_width)
        if cache_key in self.usage_cache:
            cached_data, cache_time = self.usage_cache[cache_key]
            # Use cache if less than 1 minute old
            if time.time() - cache_time < 60:
                return cached_data
        
        # Fetch from Admin API
        url = 'https://api.anthropic.com/v1/organizations/usage_report/messages'
        usage_data = self._rate_limited_request(url, params=params)
        
        # Cache the result
        self.usage_cache[cache_key] = (usage_data, time.time())
        
        return usage_data
    
    def get_cost(self, start_time=None, end_time=None):
        """
        Fetch API cost data with caching
        
        :param start_time: Optional start time for cost data
        :param end_time: Optional end time for cost data
        :return: Cost data dictionary
        """
        # Use current time if not specified, ensure proper date range
        if end_time is None:
            end_time = datetime.now(UTC)
        if start_time is None:
            start_time = end_time - timedelta(days=1)
        
        # Convert to clean ISO format strings with Z suffix (API expects this format)
        start_str = start_time.replace(microsecond=0).isoformat().replace('+00:00', 'Z')
        end_str = end_time.replace(microsecond=0).isoformat().replace('+00:00', 'Z')
        
        # Check cache first
        cache_key = (start_str, end_str)
        if cache_key in self.cost_cache:
            cached_data, cache_time = self.cost_cache[cache_key]
            # Use cache if less than 1 minute old
            if time.time() - cache_time < 60:
                return cached_data
        
        # Fetch from Admin API
        url = 'https://api.anthropic.com/v1/organizations/cost_report'
        params = {
            'starting_at': start_str,
            'ending_at': end_str,
            'bucket_width': '1d'
        }
        
        cost_data = self._rate_limited_request(url, params=params)
        
        # Cache the result
        self.cost_cache[cache_key] = (cost_data, time.time())
        
        return cost_data
    
    def get_budget_summary(self):
        """
        Generate a comprehensive budget summary
        
        :return: Dictionary with budget and usage information
        """
        # Use same time range for both API calls
        end_time = datetime.now(UTC)
        start_time = end_time - timedelta(days=1)
        
        usage = self.get_usage(start_time, end_time)
        cost = self.get_cost(start_time, end_time)
        
        # Extract meaningful data from the API response
        usage_data = usage.get('data', [])
        cost_data = cost.get('data', [])
        
        # Count total usage across all buckets
        total_messages = sum(len(bucket.get('results', [])) for bucket in usage_data)
        total_cost_items = sum(len(bucket.get('results', [])) for bucket in cost_data)
        
        return {
            'usage_buckets': len(usage_data),
            'cost_buckets': len(cost_data),
            'total_message_records': total_messages,
            'total_cost_records': total_cost_items,
            'has_more_usage': usage.get('has_more', False),
            'has_more_cost': cost.get('has_more', False),
            'timestamp': datetime.now(UTC).isoformat()
        }

def main():
    """
    Example usage and testing
    """
    parser = argparse.ArgumentParser(description='Anthropic Cost Tracker')
    parser.add_argument('--start-date', type=str, help='Start date (YYYY-MM-DD format)')
    parser.add_argument('--end-date', type=str, help='End date (YYYY-MM-DD format)')
    
    args = parser.parse_args()
    
    try:
        tracker = AnthropicCostTracker()
        
        # Parse dates if provided
        start_time = None
        end_time = None
        
        if args.start_date:
            start_time = datetime.fromisoformat(args.start_date).replace(tzinfo=UTC)
        if args.end_date:
            end_time = datetime.fromisoformat(args.end_date).replace(tzinfo=UTC)
            
        # Get usage and cost data for the specified period
        if start_time or end_time:
            print("=== USAGE DATA ===")
            try:
                # For today's data, use hourly buckets
                if start_time and start_time.date() >= datetime.now(UTC).date():
                    usage = tracker.get_usage(start_time, end_time, bucket_width='1h')
                else:
                    usage = tracker.get_usage(start_time, end_time, bucket_width='1d')
                print(json.dumps(usage, indent=2))
                
                # Extract and summarize usage
                total_input = 0
                total_output = 0
                estimated_cost = 0.0
                
                for bucket in usage.get('data', []):
                    for result in bucket.get('results', []):
                        # Sum up input tokens (cached + uncached + cache creation)
                        input_tokens = result.get('uncached_input_tokens', 0)
                        input_tokens += result.get('cache_read_input_tokens', 0)
                        if 'cache_creation' in result:
                            input_tokens += result['cache_creation'].get('ephemeral_1h_input_tokens', 0)
                            input_tokens += result['cache_creation'].get('ephemeral_5m_input_tokens', 0)
                        
                        output_tokens = result.get('output_tokens', 0)
                        total_input += input_tokens
                        total_output += output_tokens
                
                # Rough cost estimation (Claude 3.5 Sonnet pricing)
                estimated_cost = (total_input * 3.0 / 1000000) + (total_output * 15.0 / 1000000)
                
                print(f"\n=== USAGE SUMMARY ===")
                print(f"Total Input Tokens: {total_input:,}")
                print(f"Total Output Tokens: {total_output:,}")
                print(f"Estimated Cost: ${estimated_cost:.4f}")
                
            except Exception as e:
                print(f"Usage API Error: {e}")
            
            print("\n=== COST DATA ===")
            try:
                cost = tracker.get_cost(start_time, end_time)
                print(json.dumps(cost, indent=2))
            except Exception as e:
                print(f"Cost API Error: {e}")
                print("Note: Cost API may not support recent date ranges. Try dates 24+ hours old.")
        else:
            # Default behavior - budget summary
            summary = tracker.get_budget_summary()
            print(json.dumps(summary, indent=2))
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    main()
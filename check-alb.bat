@echo off
echo Checking Application Load Balancer DNS name...
aws elbv2 describe-load-balancers --query "LoadBalancers[?contains(LoadBalancerName, 'gesture-ease')].DNSName" --output table
echo.
echo If you see the DNS name above, use it to access your application:
echo http://[DNS-NAME] or https://[DNS-NAME]
pause
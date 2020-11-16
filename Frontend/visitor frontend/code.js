function submit() 
{
    var otp = document.getElementById("otp").value;
    var apigClient = apigClientFactory.newClient();
    var msg = "OTP not found, Access Denied";
	let params = {};
	var body = {
        "otp" : otp
    };
    console.log(body);
    apigClient.visitorPost(params,body)
	.then(function(result){
		console.log("result is");
		console.log(result);
        msg = result['data']['body'];
        console.log("Message is "+msg);
        document.getElementById("response").style="height:60px;width:180px;display:inline-block;font-size:20px;background: white"
        document.getElementById("response").innerHTML = '<h4 style="color:green;margin:5px">' + msg + '</h4>';
	}).catch(function(result) {
        console.log("ERROR: " + result);
        document.getElementById("response").innerHTML = msg;
    });
}
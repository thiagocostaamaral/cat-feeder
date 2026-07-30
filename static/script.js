async function testMotor(){
    const response = await fetch("/motor/test",{
        method:"POST"
    });
    const result = await response.json();
    document.getElementById("status").innerHTML =
        "Resposta: " + result.status;
}
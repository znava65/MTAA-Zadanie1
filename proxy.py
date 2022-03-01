# Eduard Znava, xznava@stuba.sk, ID: 103190
# MTAA 2021/2022, Zadanie 1


from twisted.protocols.sip import *
from twisted.internet import reactor
import socket
import logging


PORT = 6000  # port, ktory pouziva proxy


class SIPProxy(Proxy):
    # dedime z triedy Proxy, prisposobujeme funkcionalitu zadaniu
    def __init__(self, host=None, port=PORT):
        super().__init__(host, port)
        self.accounts = {}
        statusCodes[200] = 'Okay'
        statusCodes[100] = "Let's try"
        statusCodes[486] = 'Not answering'
        statusCodes[603] = 'Declined'

        logging.basicConfig(
            filename='SIP_log.txt',
            filemode='a',
            format='%(asctime)s %(levelname)s - %(message)s',
            level=logging.NOTSET
        )
        self.logger = logging.getLogger()

    def change_contact(self, contact):
        # zmena pola Contact do tvaru sip:username@user_ip:user_port
        # kvoli plnohodnotnej funkcnosti
        contact_split = contact.split(';')
        username = parseURL(contact_split[0][1:]).username
        addr = self.accounts[username]
        contact_url_split = contact_split[0].split('@')  # ziskame split url kontaktu
        contact_url_split[-1] = addr[0] + ':' + str(addr[1])
        contact_url = '@'.join(contact_url_split)
        contact_changed = ';'.join([contact_url] + contact_split[1:])

        return [contact_changed]

    @staticmethod
    def prepare_and_parseURL(url):
        if url.startswith('<'):
            url_prepared = url[1:-1]
        else:
            url_prepared = url

        return parseURL(url_prepared)

    def send_without_response(self, username, message):
        if username not in self.accounts.keys():
            self.deliverResponse(self.responseFromRequest(480, message))
        else:
            self.sendMessage(URL(host=self.accounts[username][0], port=self.accounts[username][1]), message)

    def handle_request(self, message, addr):
        if message.method not in ['REGISTER', 'SUBSCRIBE']:  # zabezpecime, aby spravy chodili cez Proxy
            message.headers['Record-Route'] = ['<sip:' + self.host + ':' + str(self.port) + ';lr=on>']
        print(message.method)
        if message.method == 'REGISTER':
            username = self.prepare_and_parseURL(message.headers['to'][0]).username
            self.accounts[username] = addr
            print(username, self.accounts[username])
            self.deliverResponse(self.responseFromRequest(200, message))

        elif message.method == 'INVITE':
            message.headers['Record-Route'] = ['<sip:' + self.host + ':' + str(PORT) + ';lr=on>']
            message.headers['contact'] = self.change_contact(message.headers['contact'][0])
            username_to = self.prepare_and_parseURL(message.headers['to'][0]).username
            if username_to not in self.accounts.keys():
                self.deliverResponse(self.responseFromRequest(480, message))
                username_from = self.prepare_and_parseURL(message.headers['from'][0][1:-1]).username
                log_message = statusCodes[480] + ', Call-ID: %s, From: %s, To: %s'
                self.logger.error(log_message, message.headers['call-id'][0], username_from, username_to)
            else:
                self.sendMessage(URL(host=self.accounts[username_to][0], port=self.accounts[username_to][1]), message)
                self.deliverResponse(self.responseFromRequest(100, message))
                username_from = self.prepare_and_parseURL(message.headers['from'][0][1:-1]).username
                log_message = message.method + ', Call-ID: %s, From: %s, To: %s'
                self.logger.info(log_message, message.headers['call-id'][0], username_from, username_to)

        elif message.method == 'CANCEL':
            username_to = self.prepare_and_parseURL(message.headers['to'][0]).username
            if username_to not in self.accounts.keys():
                self.deliverResponse(self.responseFromRequest(404, message))
            else:
                self.deliverResponse(self.responseFromRequest(200, message))
                self.sendMessage(URL(host=self.accounts[username_to][0], port=self.accounts[username_to][1]), message)
                username_from = self.prepare_and_parseURL(message.headers['from'][0][1:-1]).username
                log_message = message.method + ', Call-ID: %s, From: %s, To: %s'
                self.logger.info(log_message, message.headers['call-id'][0], username_from, username_to)

        elif message.method == 'SUBSCRIBE':
            message.headers['contact'] = self.change_contact(message.headers['contact'][0])
            username = self.prepare_and_parseURL(message.headers['to'][0]).username
            self.send_without_response(username, message)

        elif message.method == 'PUBLISH':
            self.deliverResponse(self.responseFromRequest(200, message))

        elif message.method in ['BYE', 'NOTIFY', 'REFER']:
            username = self.prepare_and_parseURL(message.headers['to'][0]).username
            self.send_without_response(username, message)

        elif message.method == 'ACK':
            username = self.prepare_and_parseURL(message.headers['to'][0]).username
            self.send_without_response(username, message)

    def handle_response(self, message, addr):
        if message.code != 100:   # kedze 100 posiela samotna proxy
            if message.code == 200 and 'contact' in message.headers.keys() and '@' in message.headers['contact'][0]:
                message.headers['contact'] = self.change_contact(message.headers['contact'][0])
            username_from = parseURL(message.headers['from'][0].split(';')[0][1:-1]).username
            if not (message.code == 200 and message.headers['cseq'][0].endswith('CANCEL')):
                self.sendMessage(URL(host=self.accounts[username_from][0], port=self.accounts[username_from][1]), message)

            # logovanie
            if message.code in [603, 486]:
                username_to = parseURL(message.headers['to'][0].split(';')[0][1:-1]).username
                log_message = str(statusCodes[message.code]) + ', Call-ID: %s, From: %s, To: %s'
                self.logger.info(log_message, message.headers['call-id'][0], username_from, username_to)

            if message.code == 200:
                username_to = parseURL(message.headers['to'][0].split(';')[0][1:-1]).username
                if message.headers['cseq'][0].endswith('INVITE'):
                    log_message = 'Start of a call, Call-ID: %s, From: %s, To: %s'
                    self.logger.info(log_message, message.headers['call-id'][0], username_from, username_to)
                elif message.headers['cseq'][0].endswith('BYE'):
                    log_message = 'End of a call, Call-ID: %s, From: %s, To: %s'
                    self.logger.info(log_message, message.headers['call-id'][0], username_from, username_to)


hostname = socket.gethostname()
ip_addr = socket.gethostbyname(hostname)
reactor.listenUDP(PORT, SIPProxy(ip_addr, PORT))
print(f'SIP Proxy launched on {ip_addr}, port {str(PORT)}')
reactor.run()
